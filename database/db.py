"""
Camada de acesso ao banco (SQLite).

Concentra a criação de conexões com PRAGMAs de performance e as tabelas
auxiliares da própria aplicação (favoritos, histórico, contadores, versões).

Para migrar a PostgreSQL, reimplemente `get_connection()` com psycopg mantendo
a mesma interface (objeto com .execute/.executemany/.commit e rows tipo dict).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

import config


def get_connection() -> sqlite3.Connection:
    """Cria uma conexão configurada para leitura rápida e acesso por nome."""
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # PRAGMAs de performance (seguros para uso local)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -65536;")  # ~64 MB de cache
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Context manager que garante commit/rollback e fechamento."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Tabelas auxiliares da aplicação (independentes da importação SIGTAP)
# --------------------------------------------------------------------------- #
APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_favoritos (
    co_procedimento TEXT PRIMARY KEY,
    criado_em       TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_historico_busca (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    termo     TEXT NOT NULL,
    filtros   TEXT,
    buscado_em TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_procedimento_hits (
    co_procedimento TEXT PRIMARY KEY,
    no_procedimento TEXT,
    hits            INTEGER DEFAULT 0,
    ultimo_acesso   TEXT
);

-- Histórico de versões importadas (competências) para comparação
CREATE TABLE IF NOT EXISTS app_versoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia   TEXT,             -- AAAAMM
    origem        TEXT,             -- nome do arquivo importado
    importado_em  TEXT DEFAULT (datetime('now','localtime')),
    is_atual      INTEGER DEFAULT 1
);

-- Snapshot enxuto de cada versão para o comparador (Maio x Junho)
CREATE TABLE IF NOT EXISTS app_snapshot (
    versao_id       INTEGER,
    co_procedimento TEXT,
    no_procedimento TEXT,
    vl_total        REAL,
    vl_sh           REAL,
    vl_sa           REAL,
    vl_sp           REAL,
    PRIMARY KEY (versao_id, co_procedimento)
);
"""


def init_app_schema() -> None:
    """Cria as tabelas auxiliares se ainda não existirem."""
    with connection() as conn:
        conn.executescript(APP_SCHEMA)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, name: str) -> list[str]:
    """Retorna a lista de colunas de uma tabela (vazia se não existir)."""
    if not table_exists(conn, name):
        return []
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{name}")')]
