"""
Importador SIGTAP.

Fluxo (`import_zip`):
  1. extrai o ZIP oficial;
  2. para cada arquivo de dados `*.txt` (que possua `*_layout.txt`), lê o layout,
     cria a tabela e carrega os registros de largura fixa;
  3. monta `procedimento_flat` (tabela desnormalizada para consultas < 1s);
  4. cria o índice de texto `procedimento_fts` (busca parcial / sem acento);
  5. registra a versão (competência) e um snapshot para o comparador.

Tudo é dinâmico: se o DATASUS acrescentar colunas/arquivos, eles são importados
automaticamente e ficam disponíveis na tela de detalhe.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Callable

import config
from database import db
from importer import layout as layout_mod
from importer.sigtap_meta import (
    DOMAIN_COMPLEXIDADE,
    DOMAIN_SEXO,
    MAIN_TABLE,
    DESC_TABLE,
)

Logger = Callable[[str], None]


# --------------------------------------------------------------------------- #
# Extração
# --------------------------------------------------------------------------- #
def _extract(zip_path: Path, log: Logger, dest: Path | None = None) -> Path:
    dest = Path(dest or config.EXTRACT_DIR)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    log(f"Extraindo {zip_path.name}…")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return dest


def _data_files(root: Path, only: set[str] | None = None) -> list[Path]:
    """Arquivos de dados (exclui os *_layout.txt). `only` filtra por nome base."""
    files = []
    for p in root.rglob("*.txt"):
        if p.name.lower().endswith("_layout.txt"):
            continue
        if only is not None and p.stem.lower() not in only:
            continue
        files.append(p)
    return sorted(files)


# Tabelas suficientes para montar procedimento_flat (usado na exportação rápida
# de uma competência, pulando as grandes tabelas de relacionamento).
FLAT_SOURCE_TABLES = {
    "tb_procedimento", "tb_descricao", "tb_grupo", "tb_sub_grupo",
    "tb_forma_organizacao", "tb_financiamento", "tb_rubrica",
    "tb_registro", "rl_procedimento_registro",
    "tb_modalidade", "rl_procedimento_modalidade",
}


# --------------------------------------------------------------------------- #
# Importação de uma tabela
# --------------------------------------------------------------------------- #
def _import_table(conn, data_file: Path, log: Logger) -> tuple[str, int] | None:
    layout_path = layout_mod.find_layout_for(data_file)
    if layout_path is None:
        log(f"  · {data_file.name}: sem layout, ignorado")
        return None
    fields = layout_mod.parse_layout(layout_path)
    table = data_file.stem.lower()

    cols_ddl = ", ".join(f'"{f.name}" {f.sql_type}' for f in fields)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({cols_ddl})')

    placeholders = ", ".join("?" for _ in fields)
    insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'

    slices = [f.slice for f in fields]
    batch, total = [], 0
    with open(data_file, "r", encoding=config.SIGTAP_ENCODING, errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            batch.append(tuple(line[s].strip() for s in slices))
            if len(batch) >= 5000:
                conn.executemany(insert_sql, batch)
                total += len(batch)
                batch.clear()
    if batch:
        conn.executemany(insert_sql, batch)
        total += len(batch)

    log(f"  · {table}: {total:,} registros".replace(",", "."))
    return table, total


# --------------------------------------------------------------------------- #
# Construção da tabela desnormalizada (procedimento_flat)
# --------------------------------------------------------------------------- #
FLAT_DDL = """
CREATE TABLE procedimento_flat (
    co_procedimento       TEXT PRIMARY KEY,
    no_procedimento       TEXT,
    descricao             TEXT,
    co_grupo              TEXT, no_grupo TEXT,
    co_sub_grupo          TEXT, no_sub_grupo TEXT,
    co_forma_organizacao  TEXT, no_forma_organizacao TEXT,
    tp_complexidade       TEXT, complexidade TEXT,
    tp_sexo               TEXT, sexo TEXT,
    qt_maxima_execucao    TEXT,
    qt_dias_permanencia   TEXT,
    qt_tempo_permanencia  TEXT,
    qt_pontos             TEXT,
    vl_idade_minima       TEXT,
    vl_idade_maxima       TEXT,
    vl_sh                 REAL,
    vl_sa                 REAL,
    vl_sp                 REAL,
    vl_total              REAL,
    co_financiamento      TEXT, no_financiamento TEXT,
    co_rubrica            TEXT, no_rubrica TEXT,
    instrumentos_registro TEXT,
    modalidades           TEXT,
    dt_competencia        TEXT
);
"""


def _money(col: str) -> str:
    """Converte o texto numérico da SIGTAP (centavos) para reais."""
    return f"CAST({col} AS REAL) / 100.0"


def _build_flat(conn, log: Logger) -> None:
    log("Montando procedimento_flat…")
    mcols = db.table_columns(conn, MAIN_TABLE)
    if not mcols:
        raise RuntimeError(f"Tabela principal '{MAIN_TABLE}' não foi importada.")

    def p(col: str, default: str = "NULL") -> str:
        return f"p.{col}" if col in mcols else default

    has = lambda t: db.table_exists(conn, t)

    # group_concat de instrumentos de registro / modalidades (se existirem)
    def concat(rl: str, dim: str, code: str, name: str, alias: str) -> str:
        if has(rl) and has(dim):
            return (
                f"(SELECT group_concat(DISTINCT d.{name}) FROM {rl} r "
                f"JOIN {dim} d ON d.{code} = r.{code} "
                f"WHERE r.co_procedimento = p.co_procedimento) AS {alias}"
            )
        return f"NULL AS {alias}"

    vl_sh = _money(p("vl_sh", "'0'"))
    vl_sa = _money(p("vl_sa", "'0'"))
    vl_sp = _money(p("vl_sp", "'0'"))

    # A coluna de descrição varia entre versões (ds_procedimento / de_procedimento)
    desc_cols = db.table_columns(conn, DESC_TABLE)
    desc_col = next((c for c in ("ds_procedimento", "de_procedimento", "de_descricao")
                     if c in desc_cols), None)
    if has(DESC_TABLE) and desc_col:
        join_desc = f"LEFT JOIN {DESC_TABLE} d ON d.co_procedimento = p.co_procedimento"
        desc_expr = f"d.{desc_col}"
    else:
        join_desc, desc_expr = "", "NULL"

    join_grp = "LEFT JOIN tb_grupo g ON g.co_grupo = substr(p.co_procedimento,1,2)" if has("tb_grupo") else ""
    no_grupo = "g.no_grupo" if has("tb_grupo") else "NULL"

    join_sub = (
        "LEFT JOIN tb_sub_grupo sg ON sg.co_grupo = substr(p.co_procedimento,1,2) "
        "AND sg.co_sub_grupo = substr(p.co_procedimento,3,2)"
        if has("tb_sub_grupo") else ""
    )
    no_sub = "sg.no_sub_grupo" if has("tb_sub_grupo") else "NULL"

    join_fo = (
        "LEFT JOIN tb_forma_organizacao fo ON fo.co_grupo = substr(p.co_procedimento,1,2) "
        "AND fo.co_sub_grupo = substr(p.co_procedimento,3,2) "
        "AND fo.co_forma_organizacao = substr(p.co_procedimento,5,2)"
        if has("tb_forma_organizacao") else ""
    )
    no_fo = "fo.no_forma_organizacao" if has("tb_forma_organizacao") else "NULL"

    join_fin = (
        f"LEFT JOIN tb_financiamento fi ON fi.co_financiamento = {p('co_financiamento')}"
        if has("tb_financiamento") and "co_financiamento" in mcols else ""
    )
    no_fin = "fi.no_financiamento" if join_fin else "NULL"

    join_rub = (
        f"LEFT JOIN tb_rubrica ru ON ru.co_rubrica = {p('co_rubrica')}"
        if has("tb_rubrica") and "co_rubrica" in mcols else ""
    )
    no_rub = "ru.no_rubrica" if join_rub else "NULL"

    # CASE de domínios (complexidade / sexo)
    def domain_case(col: str, mapping: dict) -> str:
        if col not in mcols:
            return "NULL"
        whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items() if k)
        return f"CASE p.{col} {whens} ELSE p.{col} END"

    conn.execute("DROP TABLE IF EXISTS procedimento_flat")
    conn.executescript(FLAT_DDL)

    select = f"""
    INSERT INTO procedimento_flat
    SELECT
        p.co_procedimento,
        {p('no_procedimento')},
        {desc_expr},
        substr(p.co_procedimento,1,2), {no_grupo},
        substr(p.co_procedimento,3,2), {no_sub},
        substr(p.co_procedimento,5,2), {no_fo},
        {p('tp_complexidade')}, {domain_case('tp_complexidade', DOMAIN_COMPLEXIDADE)},
        {p('tp_sexo')}, {domain_case('tp_sexo', DOMAIN_SEXO)},
        {p('qt_maxima_execucao')},
        {p('qt_dias_permanencia')},
        {p('qt_tempo_permanencia')},
        {p('qt_pontos')},
        {p('vl_idade_minima')},
        {p('vl_idade_maxima')},
        {vl_sh}, {vl_sa}, {vl_sp},
        ({vl_sh}) + ({vl_sa}) + ({vl_sp}),
        {p('co_financiamento')}, {no_fin},
        {p('co_rubrica')}, {no_rub},
        {concat('rl_procedimento_registro', 'tb_registro', 'co_registro', 'no_registro', 'ir')},
        {concat('rl_procedimento_modalidade', 'tb_modalidade', 'co_modalidade', 'no_modalidade', 'mo')},
        {p('dt_competencia')}
    FROM {MAIN_TABLE} p
    {join_desc} {join_grp} {join_sub} {join_fo} {join_fin} {join_rub}
    """
    conn.execute(select)

    # Índices para filtros/ordenção rápidos
    for col in ("co_grupo", "co_sub_grupo", "co_forma_organizacao",
                "complexidade", "sexo", "no_financiamento", "vl_total"):
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_flat_{col} ON procedimento_flat({col})")
    log("  procedimento_flat pronta.")


# --------------------------------------------------------------------------- #
# Índice de busca textual (FTS5)
# --------------------------------------------------------------------------- #
def _build_fts(conn, log: Logger) -> None:
    log("Criando índice de busca (FTS5)…")
    conn.execute("DROP TABLE IF EXISTS procedimento_fts")
    conn.execute(
        "CREATE VIRTUAL TABLE procedimento_fts USING fts5("
        "co_procedimento UNINDEXED, no_procedimento, descricao, "
        "tokenize = 'unicode61 remove_diacritics 2')"
    )
    conn.execute(
        "INSERT INTO procedimento_fts (co_procedimento, no_procedimento, descricao) "
        "SELECT co_procedimento, no_procedimento, descricao FROM procedimento_flat"
    )
    log("  índice pronto.")


# --------------------------------------------------------------------------- #
# Versionamento / snapshot
# --------------------------------------------------------------------------- #
def _register_version(conn, competencia: str, origem: str, log: Logger) -> int:
    conn.execute("UPDATE app_versoes SET is_atual = 0")
    cur = conn.execute(
        "INSERT INTO app_versoes (competencia, origem, is_atual) VALUES (?,?,1)",
        (competencia, origem),
    )
    vid = cur.lastrowid
    conn.execute(
        "INSERT INTO app_snapshot "
        "SELECT ?, co_procedimento, no_procedimento, vl_total, vl_sh, vl_sa, vl_sp "
        "FROM procedimento_flat",
        (vid,),
    )
    log(f"Versão registrada (competência {competencia}, id {vid}).")
    return vid


def _guess_competencia(zip_path: Path) -> str:
    import re
    m = re.search(r"(\d{6})", zip_path.name)
    return m.group(1) if m else "000000"


# --------------------------------------------------------------------------- #
# Ponto de entrada
# --------------------------------------------------------------------------- #
def import_zip(zip_path: str | Path, competencia: str | None = None,
               log: Logger = print) -> dict:
    """Importa um ZIP oficial da SIGTAP para o banco local."""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    competencia = competencia or _guess_competencia(zip_path)

    db.init_app_schema()
    root = _extract(zip_path, log)
    files = _data_files(root)
    log(f"{len(files)} arquivos de dados encontrados.")

    imported: dict[str, int] = {}
    with db.connection() as conn:
        for f in files:
            try:
                res = _import_table(conn, f, log)
                if res:
                    imported[res[0]] = res[1]
            except Exception as exc:  # noqa: BLE001 — um arquivo ruim não aborta a base
                log(f"  ! {f.name}: ignorado ({exc})")
        _build_flat(conn, log)
        _build_fts(conn, log)
        vid = _register_version(conn, competencia, zip_path.name, log)
        conn.execute("ANALYZE")

    log("Importação concluída com sucesso.")
    return {
        "competencia": competencia,
        "versao_id": vid,
        "tabelas": imported,
        "total_procedimentos": imported.get(MAIN_TABLE, 0),
    }


def build_flat_isolated(zip_path: str | Path, db_path: str | Path,
                        extract_dir: Path, only_flat: bool = True,
                        log: Logger = print) -> int:
    """
    Importa um ZIP para um banco SQLite SEPARADO (não toca na base ativa) e
    monta `procedimento_flat`. Usado para exportar uma competência qualquer.

    Retorna a quantidade de procedimentos. Com `only_flat=True`, importa apenas
    as tabelas necessárias para a planilha (bem mais rápido).
    """
    import sqlite3

    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    root = _extract(zip_path, log, dest=extract_dir)
    only = FLAT_SOURCE_TABLES if only_flat else None
    files = _data_files(root, only=only)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for f in files:
            try:
                _import_table(conn, f, log)
            except Exception as exc:  # noqa: BLE001
                log(f"  ! {f.name}: ignorado ({exc})")
        _build_flat(conn, log)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) c FROM procedimento_flat").fetchone()["c"]
    finally:
        conn.close()
    return n
