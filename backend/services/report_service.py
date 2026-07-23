"""
Relatórios gerenciais.

Cada função devolve {"title", "columns", "rows"} pronto para exibir e exportar.
"""
from __future__ import annotations

from database import db


def _q(sql: str, params: tuple = ()) -> list[dict]:
    with db.connection() as conn:
        if not db.table_exists(conn, "procedimento_flat"):
            return []
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mais_pesquisados(limit: int = 50) -> dict:
    with db.connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT co_procedimento, no_procedimento, hits, ultimo_acesso "
            "FROM app_procedimento_hits ORDER BY hits DESC LIMIT ?", (limit,)
        ).fetchall()]
    return {"title": "Procedimentos mais pesquisados",
            "columns": ["co_procedimento", "no_procedimento", "hits", "ultimo_acesso"],
            "rows": rows}


def por_grupo() -> dict:
    rows = _q(
        "SELECT co_grupo, no_grupo, COUNT(*) qtd, "
        "ROUND(SUM(vl_total),2) soma_total "
        "FROM procedimento_flat GROUP BY co_grupo, no_grupo ORDER BY co_grupo"
    )
    return {"title": "Procedimentos por Grupo",
            "columns": ["co_grupo", "no_grupo", "qtd", "soma_total"], "rows": rows}


def por_financiamento() -> dict:
    rows = _q(
        "SELECT no_financiamento, COUNT(*) qtd, ROUND(SUM(vl_total),2) soma_total "
        "FROM procedimento_flat GROUP BY no_financiamento ORDER BY qtd DESC"
    )
    return {"title": "Produção por Tipo de Financiamento",
            "columns": ["no_financiamento", "qtd", "soma_total"], "rows": rows}


def honorarios_medicos() -> dict:
    """Tabela de honorários (valor profissional > 0)."""
    rows = _q(
        "SELECT co_procedimento, no_procedimento, vl_sp, vl_sh, vl_total "
        "FROM procedimento_flat WHERE vl_sp > 0 ORDER BY vl_sp DESC"
    )
    return {"title": "Tabela de Honorários Médicos (Valor Profissional)",
            "columns": ["co_procedimento", "no_procedimento", "vl_sp", "vl_sh", "vl_total"],
            "rows": rows}


def tabela_hospitalar() -> dict:
    rows = _q(
        "SELECT co_procedimento, no_procedimento, vl_sh, vl_sp, vl_total "
        "FROM procedimento_flat WHERE vl_sh > 0 ORDER BY vl_sh DESC"
    )
    return {"title": "Tabela Hospitalar (Valor Hospitalar)",
            "columns": ["co_procedimento", "no_procedimento", "vl_sh", "vl_sp", "vl_total"],
            "rows": rows}


def lista_completa() -> dict:
    rows = _q(
        "SELECT co_procedimento, no_procedimento, no_grupo, no_sub_grupo, "
        "complexidade, vl_total FROM procedimento_flat ORDER BY co_procedimento"
    )
    return {"title": "Lista Completa de Procedimentos",
            "columns": ["co_procedimento", "no_procedimento", "no_grupo",
                        "no_sub_grupo", "complexidade", "vl_total"], "rows": rows}


REPORTS = {
    "mais_pesquisados": mais_pesquisados,
    "por_grupo": por_grupo,
    "por_financiamento": por_financiamento,
    "honorarios_medicos": honorarios_medicos,
    "tabela_hospitalar": tabela_hospitalar,
    "lista_completa": lista_completa,
}


def run(name: str) -> dict:
    fn = REPORTS.get(name)
    if not fn:
        raise KeyError(name)
    return fn()
