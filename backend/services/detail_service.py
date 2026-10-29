"""
Serviço de detalhe do procedimento.

Reúne TODOS os campos existentes na base para um procedimento:
  * dados principais (procedimento_flat + linha crua de tb_procedimento);
  * separação clara dos valores (Total / SH / SA / SP / incrementos);
  * todas as tabelas de relacionamento (CID, CBO, serviços, habilitações,
    compatibilidades, incrementos, regras, RENASES, leitos, detalhes…),
    com os códigos enriquecidos pelo nome quando há tabela de domínio.
"""
from __future__ import annotations

from database import db
from importer.sigtap_meta import MAIN_TABLE, DETAIL_SECTIONS, COLUMN_LABELS

COMPAT_TABLE = "rl_procedimento_compativel"
GRUPO_OPME = "07"            # Órteses, próteses e materiais especiais


def _dim_lookup(conn, code_col: str, codes: set[str]) -> dict[str, str]:
    """Para 'co_cid' procura 'tb_cid'.'no_cid' e devolve {codigo: nome}."""
    if not codes or not code_col.startswith("co_"):
        return {}
    suffix = code_col[3:]                      # cid, ocupacao, registro…
    dim = f"tb_{suffix}"
    name_col = f"no_{suffix}"
    if not db.table_exists(conn, dim):
        return {}
    cols = db.table_columns(conn, dim)
    if code_col not in cols or name_col not in cols:
        return {}
    qs = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"SELECT {code_col} c, {name_col} n FROM {dim} WHERE {code_col} IN ({qs})",
        tuple(codes),
    ).fetchall()
    return {r["c"]: r["n"] for r in rows}


def _load_section(conn, table: str, code: str) -> dict | None:
    if not db.table_exists(conn, table):
        return None
    cols = db.table_columns(conn, table)
    if "co_procedimento" not in cols:
        return None
    rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM {table} WHERE co_procedimento = ?", (code,)
    ).fetchall()]
    if not rows:
        return None

    # Enriquecimento: para cada coluna co_* com tabela de domínio, adiciona _nome
    for col in cols:
        if col in ("co_procedimento",) or not col.startswith("co_"):
            continue
        codes = {r[col] for r in rows if r.get(col)}
        lookup = _dim_lookup(conn, col, codes)
        if lookup:
            for r in rows:
                r[f"{col}__nome"] = lookup.get(r.get(col))
    return {"table": table, "rows": rows, "columns": list(rows[0].keys())}


def _registro_nomes(conn) -> dict[str, str]:
    if not db.table_exists(conn, "tb_registro"):
        return {}
    return {r["co_registro"]: r["no_registro"] for r in conn.execute(
        "SELECT co_registro, no_registro FROM tb_registro").fetchall()}


def _compat_rows(conn, code: str, reverse: bool) -> list[dict]:
    """Linhas de rl_procedimento_compativel.

    A tabela não tem CO_PROCEDIMENTO: liga por CO_PROCEDIMENTO_PRINCIPAL e
    CO_PROCEDIMENTO_COMPATIVEL. Com reverse=False devolve o que entra no
    procedimento (materiais/OPME e demais compatíveis); com reverse=True,
    os procedimentos em que este item pode ser cobrado.
    """
    outro = "co_procedimento_principal" if reverse else "co_procedimento_compativel"
    filtro = "co_procedimento_compativel" if reverse else "co_procedimento_principal"
    rows = [dict(r) for r in conn.execute(
        f"""SELECT c.{outro} AS {outro},
                   pf.no_procedimento,
                   pf.no_grupo,
                   pf.vl_total,
                   c.qt_permitida,
                   c.co_registro_principal,
                   c.co_registro_compativel,
                   c.tp_compatibilidade
              FROM {COMPAT_TABLE} c
              LEFT JOIN procedimento_flat pf ON pf.co_procedimento = c.{outro}
             WHERE c.{filtro} = ?
             ORDER BY c.{outro}""", (code,)).fetchall()]

    nomes = _registro_nomes(conn)
    for r in rows:
        qt = (r.get("qt_permitida") or "").lstrip("0")
        r["qt_permitida"] = qt or r.get("qt_permitida")
        r["no_registro_principal"] = nomes.get(
            r.pop("co_registro_principal", None)) or ""
        r["no_registro_compativel"] = nomes.get(
            r.pop("co_registro_compativel", None)) or ""
    return rows


def _compat_sections(conn, code: str) -> list[dict]:
    """Seções de compatibilidade, com os materiais/OPME em destaque."""
    if not db.table_exists(conn, COMPAT_TABLE):
        return []

    entram = _compat_rows(conn, code, reverse=False)
    def _is_opme(r):
        return (r["co_procedimento_compativel"] or "").startswith(GRUPO_OPME)
    opme = [r for r in entram if _is_opme(r)]
    outros = [r for r in entram if not _is_opme(r)]
    for r in opme:                      # todos são do grupo 07, coluna redundante
        r.pop("no_grupo", None)
    usado_em = _compat_rows(conn, code, reverse=True)

    grupos = [
        (opme, "Materiais / OPME compatíveis"),
        (outros, "Outros procedimentos compatíveis"),
        (usado_em, "Compatível com (pode ser cobrado junto de)"),
    ]
    return [{"table": COMPAT_TABLE, "title": title,
             "rows": rows, "columns": list(rows[0].keys())}
            for rows, title in grupos if rows]


def get_detail(code: str) -> dict | None:
    with db.connection() as conn:
        if not db.table_exists(conn, "procedimento_flat"):
            return None
        flat = conn.execute(
            "SELECT * FROM procedimento_flat WHERE co_procedimento = ?", (code,)
        ).fetchone()
        if flat is None:
            return None
        flat = dict(flat)

        raw = {}
        if db.table_exists(conn, MAIN_TABLE):
            r = conn.execute(
                f"SELECT * FROM {MAIN_TABLE} WHERE co_procedimento = ?", (code,)
            ).fetchone()
            raw = dict(r) if r else {}

        sections = []
        for table, title in DETAIL_SECTIONS:
            if table == COMPAT_TABLE:
                sections.extend(_compat_sections(conn, code))
                continue
            sec = _load_section(conn, table, code)
            if sec:
                sec["title"] = title
                sections.append(sec)

    valores = {
        "vl_total": flat.get("vl_total"),
        "vl_sh": flat.get("vl_sh"),
        "vl_sa": flat.get("vl_sa"),
        "vl_sp": flat.get("vl_sp"),
        "financiamento": flat.get("no_financiamento"),
    }

    return {
        "flat": flat,
        "raw": raw,
        "valores": valores,
        "sections": sections,
        "labels": COLUMN_LABELS,
    }
