"""
Ponto de entrada do SIGTAP Local.

Uso:
    python run.py                 # sobe a aplicação web (http://127.0.0.1:5000)
    python run.py import ARQ.zip  # importa um ZIP oficial pela linha de comando
    python run.py update          # baixa a competência mais recente e importa
"""
from __future__ import annotations

import sys

import config


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] == "import":
        if len(args) < 2:
            print("Uso: python run.py import CAMINHO_DO_ZIP")
            sys.exit(1)
        from importer import importer
        importer.import_zip(args[1])
        return

    if args and args[0] == "update":
        from importer import downloader, importer
        zip_path, comp = downloader.download_latest()
        importer.import_zip(zip_path, comp)
        return

    # Modo web (padrão)
    from backend.app import create_app
    app = create_app()
    print(f"SIGTAP Local rodando em http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()
