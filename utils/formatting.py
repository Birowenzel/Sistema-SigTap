"""Utilitários de formatação (valores em Real, competência, etc.)."""
from __future__ import annotations


def brl(value) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    s = f"{v:,.2f}"                       # 1,234.50
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def competencia_label(comp: str | None) -> str:
    """'202406' -> '06/2024'."""
    if not comp or len(comp) != 6:
        return comp or "—"
    return f"{comp[4:]}/{comp[:4]}"
