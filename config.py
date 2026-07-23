"""
Configuração central do SIGTAP Local.

Todos os caminhos e parâmetros ajustáveis ficam aqui para facilitar a manutenção.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Diretórios
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"      # ZIPs baixados do DATASUS
EXTRACT_DIR = DATA_DIR / "extract"         # arquivos extraídos temporariamente
EXPORT_DIR = DATA_DIR / "exports"          # arquivos gerados (xlsx/csv/pdf)
COMPETENCIAS_DIR = DATA_DIR / "competencias"  # ZIPs mensais guardados p/ exportar

DB_PATH = DATA_DIR / "sigtap.db"           # banco SQLite principal

for _d in (DATA_DIR, DOWNLOAD_DIR, EXTRACT_DIR, EXPORT_DIR, COMPETENCIAS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Pastas onde o sistema procura ZIPs de competências para exportar
COMPETENCIA_SEARCH_DIRS = [COMPETENCIAS_DIR, DOWNLOAD_DIR, BASE_DIR]

# --------------------------------------------------------------------------- #
# Banco de dados
# --------------------------------------------------------------------------- #
# Para migrar para PostgreSQL, troque a camada database/db.py por um driver
# psycopg e ajuste os tipos em importer/importer.py (o restante é agnóstico).
DB_ENGINE = "sqlite"

# --------------------------------------------------------------------------- #
# Download DATASUS
# --------------------------------------------------------------------------- #
# O DATASUS publica os pacotes mensais ("competências") da Tabela Unificada em
# ftp2.datasus.gov.br. Nome do arquivo: TabelaUnificada_AAAAMM_vNNN.zip
#
# O acesso direto costuma ser bloqueado por firewall hospitalar; o downloader
# tenta os endereços abaixo em ordem (FTP e HTTP). Você pode:
#   * definir SIGTAP_BASE_URL para forçar um endereço (ex.: mirror interno);
#   * definir SIGTAP_PROXY com o proxy corporativo (ex.: http://proxy:8080).
_DEFAULT_CANDIDATES = [
    "ftp://ftp2.datasus.gov.br/public/sistemas/tup/downloads/",
    "http://ftp2.datasus.gov.br/public/sistemas/tup/downloads/",
    "https://ftp2.datasus.gov.br/public/sistemas/tup/downloads/",
]
_forced = os.environ.get("SIGTAP_BASE_URL", "").strip()
DATASUS_CANDIDATES = [_forced] + _DEFAULT_CANDIDATES if _forced else _DEFAULT_CANDIDATES

DATASUS_PROXY = os.environ.get("SIGTAP_PROXY", "").strip() or None
DATASUS_TIMEOUT = 45  # segundos por tentativa

# Codificação dos arquivos oficiais (fixed-width) da SIGTAP
SIGTAP_ENCODING = "latin-1"

# --------------------------------------------------------------------------- #
# Aplicação web
# --------------------------------------------------------------------------- #
HOST = os.environ.get("SIGTAP_HOST", "127.0.0.1")
# Aceita PORT (usado por ferramentas de preview) ou SIGTAP_PORT
PORT = int(os.environ.get("PORT") or os.environ.get("SIGTAP_PORT") or "5000")
DEBUG = os.environ.get("SIGTAP_DEBUG", "0") == "1"
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 500
