"""
Serviço de competências: exportar QUALQUER competência (arquivo ZIP da SIGTAP)
para planilha, sem alterar a base ativa.

Fluxo de exportação:
  1. o ZIP é aberto num banco SQLite TEMPORÁRIO e isolado;
  2. monta-se `procedimento_flat` (só as tabelas necessárias → rápido);
  3. gera-se o arquivo (xlsx/csv) via exporters;
  4. o banco e a extração temporários são descartados.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import config
from importer import importer
from exporters import exporters

_COMP_RE = re.compile(r"TabelaUnificada_(\d{6})", re.IGNORECASE)

# Colunas exportadas (mesma ordem da consulta)
EXPORT_COLUMNS = [
    "co_procedimento", "no_procedimento", "no_grupo", "no_sub_grupo",
    "no_forma_organizacao", "complexidade", "sexo", "no_financiamento",
    "vl_sh", "vl_sa", "vl_sp", "vl_total",
]

_MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
          "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _competencia_of(name: str) -> str | None:
    m = _COMP_RE.search(name)
    return m.group(1) if m else None


def _label(comp: str) -> str:
    if not comp or len(comp) != 6:
        return comp or "?"
    ano, mes = comp[:4], int(comp[4:])
    nome = _MESES[mes] if 1 <= mes <= 12 else comp[4:]
    return f"{nome}/{ano}"


def list_zips() -> list[dict]:
    """Lista os ZIPs de competência encontrados nas pastas de busca."""
    seen: dict[str, dict] = {}
    for folder in config.COMPETENCIA_SEARCH_DIRS:
        folder = Path(folder)
        if not folder.exists():
            continue
        for zp in folder.glob("TabelaUnificada_*.zip"):
            comp = _competencia_of(zp.name)
            if not comp:
                continue
            # se houver o mesmo mês em pastas diferentes, mantém o primeiro achado
            if comp in seen:
                continue
            seen[comp] = {
                "competencia": comp,
                "label": _label(comp),
                "ano": comp[:4],
                "mes": comp[4:],
                "filename": zp.name,
                "path": str(zp),
                "tamanho_mb": round(zp.stat().st_size / (1024 * 1024), 1),
            }
    return sorted(seen.values(), key=lambda x: x["competencia"], reverse=True)


def _resolve_zip(filename: str) -> Path:
    """Valida que o arquivo pedido está numa pasta permitida (evita path traversal)."""
    name = Path(filename).name  # descarta qualquer diretório do input
    for folder in config.COMPETENCIA_SEARCH_DIRS:
        cand = Path(folder) / name
        if cand.exists():
            return cand
    raise FileNotFoundError(f"Competência não encontrada: {name}")


def export_zip(zip_path: str | Path, fmt: str = "xlsx", log=lambda *_: None) -> Path:
    """Importa o ZIP num banco temporário e exporta a planilha da competência."""
    import sqlite3

    zip_path = Path(zip_path)
    comp = _competencia_of(zip_path.name) or "000000"

    tmp_extract = Path(tempfile.mkdtemp(prefix=f"sigtap_{comp}_", dir=config.EXTRACT_DIR))
    fd, tmp_db = tempfile.mkstemp(suffix=".db", prefix=f"sigtap_{comp}_", dir=config.EXTRACT_DIR)
    import os
    os.close(fd)

    try:
        n = importer.build_flat_isolated(zip_path, tmp_db, tmp_extract, only_flat=True, log=log)
        log(f"{n} procedimentos na competência {comp}.")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM procedimento_flat ORDER BY co_procedimento")]
        finally:
            conn.close()

        title = f"SIGTAP {_label(comp)}"
        path = exporters.export(fmt, EXPORT_COLUMNS, rows,
                                prefix=f"SIGTAP_{comp}", title=title)
        return path
    finally:
        # limpeza dos temporários
        import shutil
        shutil.rmtree(tmp_extract, ignore_errors=True)
        try:
            Path(tmp_db).unlink(missing_ok=True)
        except OSError:
            pass


def export_by_filename(filename: str, fmt: str = "xlsx") -> Path:
    return export_zip(_resolve_zip(filename), fmt)
