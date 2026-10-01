"""
Serviço de consulta de procedimentos.

Combina o índice FTS5 (busca textual parcial, sem acento) com a tabela
desnormalizada `procedimento_flat` (filtros, ordenação, paginação).
"""
from __future__ import annotations

import re

import config
from database import db
from importer.sigtap_meta import FILTERS

# Colunas permitidas para ordenação (evita SQL injection no ORDER BY)
SORTABLE = {
    "co_procedimento", "no_procedimento", "no_grupo", "no_sub_grupo",
    "no_forma_organizacao", "complexidade", "sexo", "vl_total",
    "vl_sh", "vl_sa", "vl_sp", "no_financiamento",
}

FILTER_COLUMNS = {f["column"] for f in FILTERS}
_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+")


def _match_expr(term: str) -> str:
    """Monta a expressão MATCH do FTS5 com prefixo (busca parcial)."""
    tokens = _TOKEN_RE.findall(term or "")
    if not tokens:
        return ""
    # cada token vira um prefixo obrigatório: "endoscop"* "digest"*
    return " ".join(f'"{t}"*' for t in tokens)


def search(term: str = "", filters: dict | None = None, page: int = 1,
           page_size: int = config.PAGE_SIZE_DEFAULT, sort_by: str = "no_procedimento",
           sort_dir: str = "asc") -> dict:
    filters = filters or {}
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), config.PAGE_SIZE_MAX)
    offset = (page - 1) * page_size

    sort_by = sort_by if sort_by in SORTABLE else "no_procedimento"
    sort_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

    where, params = [], []

    match = _match_expr(term)
    if match:
        # Casa no índice textual (nome/descrição) OU por prefixo de código.
        # Ex.: "0209" traz todos os procedimentos que começam por 0209.
        code_prefix = "".join(term.split())
        where.append(
            "(f.co_procedimento IN "
            " (SELECT co_procedimento FROM procedimento_fts WHERE procedimento_fts MATCH ?) "
            " OR f.co_procedimento LIKE ?)"
        )
        params.extend([match, code_prefix + "%"])

    for f in FILTERS:
        val = filters.get(f["key"])
        if val:
            where.append(f'f.{f["column"]} = ?')
            params.append(val)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db.connection() as conn:
        if not db.table_exists(conn, "procedimento_flat"):
            return {"rows": [], "total": 0, "page": page, "page_size": page_size,
                    "pages": 0, "empty_db": True}

        total = conn.execute(
            f"SELECT COUNT(*) c FROM procedimento_flat f {where_sql}", params
        ).fetchone()["c"]

        rows = conn.execute(
            f"SELECT * FROM procedimento_flat f {where_sql} "
            f"ORDER BY f.{sort_by} {sort_dir} LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()

    return {
        "rows": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def search_all_codes(term: str = "", filters: dict | None = None) -> list[str]:
    """Todos os códigos que casam com a busca/filtros (usado na exportação)."""
    res = search(term, filters, page=1, page_size=config.PAGE_SIZE_MAX)
    codes = [r["co_procedimento"] for r in res["rows"]]
    # pagina o restante
    page = 2
    while len(codes) < res["total"]:
        more = search(term, filters, page=page, page_size=config.PAGE_SIZE_MAX)
        if not more["rows"]:
            break
        codes += [r["co_procedimento"] for r in more["rows"]]
        page += 1
    return codes


def filter_options() -> list[dict]:
    """Opções para os filtros laterais (código + nome distintos)."""
    out = []
    with db.connection() as conn:
        if not db.table_exists(conn, "procedimento_flat"):
            return []
        for f in FILTERS:
            code, name = f["opt_code"], f["opt_name"]
            rows = conn.execute(
                f"SELECT DISTINCT {code} AS code, {name} AS name "
                f"FROM procedimento_flat WHERE {code} IS NOT NULL AND {code} <> '' "
                f"ORDER BY name"
            ).fetchall()
            out.append({
                "key": f["key"], "label": f["label"],
                "options": [{"value": r["code"], "label": r["name"] or r["code"]}
                            for r in rows],
            })
    return out
