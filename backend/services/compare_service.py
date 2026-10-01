"""
Comparação entre duas versões (competências) da SIGTAP.

Usa a tabela `app_snapshot`, gravada a cada importação, para detectar:
  * procedimentos adicionados;
  * procedimentos removidos;
  * mudanças de valor (Total / SH / SA / SP);
  * mudança de nome.
"""
from __future__ import annotations

from database import db


def list_versions() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, competencia, origem, importado_em, is_atual "
            "FROM app_versoes ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def _snapshot(conn, versao_id: int) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT co_procedimento, no_procedimento, vl_total, vl_sh, vl_sa, vl_sp "
        "FROM app_snapshot WHERE versao_id = ?", (versao_id,)
    ).fetchall()
    return {r["co_procedimento"]: dict(r) for r in rows}


def compare(versao_a: int, versao_b: int) -> dict:
    """Compara A (anterior) x B (posterior)."""
    with db.connection() as conn:
        a = _snapshot(conn, versao_a)
        b = _snapshot(conn, versao_b)

    added, removed, changed = [], [], []
    for code, rb in b.items():
        if code not in a:
            added.append(rb)
        else:
            ra = a[code]
            diffs = {}
            for fld in ("vl_total", "vl_sh", "vl_sa", "vl_sp"):
                if round(ra[fld] or 0, 2) != round(rb[fld] or 0, 2):
                    diffs[fld] = {"de": ra[fld], "para": rb[fld]}
            if (ra["no_procedimento"] or "") != (rb["no_procedimento"] or ""):
                diffs["no_procedimento"] = {"de": ra["no_procedimento"],
                                            "para": rb["no_procedimento"]}
            if diffs:
                changed.append({"co_procedimento": code,
                                "no_procedimento": rb["no_procedimento"],
                                "mudancas": diffs})
    for code, ra in a.items():
        if code not in b:
            removed.append(ra)

    return {
        "resumo": {"adicionados": len(added), "removidos": len(removed),
                   "alterados": len(changed)},
        "adicionados": sorted(added, key=lambda r: r["co_procedimento"]),
        "removidos": sorted(removed, key=lambda r: r["co_procedimento"]),
        "alterados": sorted(changed, key=lambda r: r["co_procedimento"]),
    }
