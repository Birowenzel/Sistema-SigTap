"""
Fábrica da aplicação Flask do SIGTAP Local.

Serve o frontend (templates/estáticos) e registra o blueprint da API.
Também mantém o estado do job de "Atualizar SIGTAP" (download + importação)
executado em segundo plano para não travar a requisição HTTP.
"""
from __future__ import annotations

import threading
from pathlib import Path

from flask import Flask

import config
from database import db

# Estado global do job de atualização (thread-safe o suficiente para uso local)
UPDATE_JOB = {
    "running": False,
    "log": [],
    "result": None,
    "error": None,
}
_JOB_LOCK = threading.Lock()


def job_log(msg: str) -> None:
    with _JOB_LOCK:
        UPDATE_JOB["log"].append(msg)
    print("[atualizar]", msg)


def run_update(source_zip: str | None = None) -> None:
    """Executa download (se necessário) + importação em segundo plano."""
    from importer import downloader, importer

    with _JOB_LOCK:
        if UPDATE_JOB["running"]:
            return
        UPDATE_JOB.update(running=True, log=[], result=None, error=None)

    def worker():
        try:
            if source_zip:
                zip_path = Path(source_zip)
                competencia = None
                job_log(f"Importação manual: {zip_path.name}")
            else:
                job_log("Consultando DATASUS…")
                zip_path, competencia = downloader.download_latest(log=job_log)
                job_log(f"Baixado: {zip_path.name}")
            result = importer.import_zip(zip_path, competencia, log=job_log)
            with _JOB_LOCK:
                UPDATE_JOB["result"] = result
        except Exception as exc:  # noqa: BLE001
            job_log(f"ERRO: {exc}")
            with _JOB_LOCK:
                UPDATE_JOB["error"] = str(exc)
        finally:
            with _JOB_LOCK:
                UPDATE_JOB["running"] = False
            job_log("Finalizado.")

    threading.Thread(target=worker, daemon=True).start()


def create_app() -> Flask:
    frontend = config.BASE_DIR / "frontend"
    app = Flask(
        __name__,
        template_folder=str(frontend / "templates"),
        static_folder=str(frontend / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # ZIP até 300 MB

    db.init_app_schema()

    from backend.api.routes import bp as api_bp
    app.register_blueprint(api_bp)

    from flask import render_template

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
