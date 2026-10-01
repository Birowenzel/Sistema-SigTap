"""
Exportadores: Excel (.xlsx), CSV e PDF.

Todas as funções recebem (columns, rows, title) e devolvem o caminho do arquivo
gerado em data/exports/. Os filtros da consulta são respeitados porque quem monta
`rows` é o chamador (ver backend/api/routes.py -> /api/export).
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

import config
from importer.sigtap_meta import COLUMN_LABELS


def _stamp(prefix: str, ext: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return config.EXPORT_DIR / f"{prefix}_{ts}.{ext}"


def _header(col: str) -> str:
    return COLUMN_LABELS.get(col, col.replace("_", " ").title())


def to_csv(columns: list[str], rows: list[dict], prefix: str = "sigtap") -> Path:
    path = _stamp(prefix, "csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow([_header(c) for c in columns])
        for r in rows:
            writer.writerow([r.get(c, "") for c in columns])
    return path


def to_xlsx(columns: list[str], rows: list[dict], prefix: str = "sigtap",
            title: str = "SIGTAP") -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    path = _stamp(prefix, "xlsx")
    wb = Workbook()
    ws = wb.active
    # Excel não aceita  \ / ? * [ ] :  no nome da aba
    ws.title = re.sub(r"[\\/?*\[\]:]", "-", title)[:31] or "SIGTAP"

    head_fill = PatternFill("solid", fgColor="1F4E78")
    head_font = Font(bold=True, color="FFFFFF")
    for j, col in enumerate(columns, 1):
        c = ws.cell(row=1, column=j, value=_header(col))
        c.fill, c.font = head_fill, head_font
        c.alignment = Alignment(horizontal="center")

    for i, r in enumerate(rows, 2):
        for j, col in enumerate(columns, 1):
            ws.cell(row=i, column=j, value=r.get(col))

    # largura automática simples
    for j, col in enumerate(columns, 1):
        width = max(len(_header(col)),
                    *(len(str(r.get(col, ""))) for r in rows[:200]), 8) + 2
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = min(width, 60)
    ws.freeze_panes = "A2"
    wb.save(path)
    return path


def to_pdf(columns: list[str], rows: list[dict], prefix: str = "sigtap",
           title: str = "SIGTAP") -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    path = _stamp(prefix, "pdf")
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]),
                Paragraph(f"Gerado em {datetime.now():%d/%m/%Y %H:%M} — "
                          f"{len(rows)} registros", styles["Normal"]),
                Spacer(1, 8)]

    # limita colunas para caber; PDF é para visão resumida
    cols = columns[:8]
    data = [[_header(c) for c in cols]]
    for r in rows[:2000]:                       # trava de segurança para PDFs enormes
        data.append([str(r.get(c, "") or "") for c in cols])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FB")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)
    if len(rows) > 2000:
        elements.append(Paragraph(
            f"* PDF truncado em 2000 de {len(rows)} registros. "
            f"Use Excel/CSV para a lista completa.", styles["Italic"]))
    doc.build(elements)
    return path


EXPORTERS = {"csv": to_csv, "xlsx": to_xlsx, "pdf": to_pdf}


def export(fmt: str, columns: list[str], rows: list[dict],
           prefix: str = "sigtap", title: str = "SIGTAP") -> Path:
    fmt = fmt.lower()
    if fmt == "csv":
        return to_csv(columns, rows, prefix)
    if fmt == "xlsx":
        return to_xlsx(columns, rows, prefix, title)
    if fmt == "pdf":
        return to_pdf(columns, rows, prefix, title)
    raise ValueError(f"Formato não suportado: {fmt}")
