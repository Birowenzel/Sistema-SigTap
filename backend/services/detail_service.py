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
