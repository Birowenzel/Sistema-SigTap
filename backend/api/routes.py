"""
Blueprint da API REST (JSON) do SIGTAP Local.

Endpoints:
  Consulta      GET  /api/search, /api/procedimento/<code>, /api/filters, /api/meta
  Favoritos     GET/POST/DELETE /api/favoritos[/<code>]
  Histórico     GET  /api/historico
  Versões       GET  /api/versoes, GET /api/compare
  Relatórios    GET  /api/relatorio/<name>
  Exportação    GET  /api/export
  Atualização   POST /api/atualizar, POST /api/importar, GET /api/status
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

import config
from database import db
from backend.services import (
    query_service, detail_service, compare_service, report_service,
    competencia_service,
)
from importer.sigtap_meta import FILTERS
from exporters import exporters

bp = Blueprint("api", __name__, url_prefix="/api")


def _filters_from_request() -> dict:
    return {f["key"]: request.args.get(f["key"], "").strip()
            for f in FILTERS if request.args.get(f["key"], "").strip()}


# --------------------------------------------------------------------------- #
# Consulta
# --------------------------------------------------------------------------- #
@bp.get("/search")
def search():
    term = request.args.get("q", "").strip()
    filters = _filters_from_request()
    result = query_service.search(
        term=term,
        filters=filters,
        page=request.args.get("page", 1, type=int),
        page_size=request.args.get("page_size", config.PAGE_SIZE_DEFAULT, type=int),
        sort_by=request.args.get("sort_by", "no_procedimento"),
        sort_dir=request.args.get("sort_dir", "asc"),
    )
    # registra histórico apenas de buscas com termo
    if term:
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO app_historico_busca (termo, filtros) VALUES (?,?)",
                (term, ",".join(f"{k}={v}" for k, v in filters.items())),
            )
    return jsonify(result)


@bp.get("/procedimento/<code>")
def procedimento(code: str):
    detail = detail_service.get_detail(code)
    if detail is None:
        return jsonify({"error": "Procedimento não encontrado"}), 404
    # contador de acessos (relatório "mais pesquisados")
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO app_procedimento_hits (co_procedimento, no_procedimento, hits, ultimo_acesso) "
            "VALUES (?,?,1,datetime('now','localtime')) "
            "ON CONFLICT(co_procedimento) DO UPDATE SET "
            "hits = hits + 1, ultimo_acesso = datetime('now','localtime')",
            (code, detail["flat"].get("no_procedimento")),
        )
    return jsonify(detail)


@bp.get("/filters")
def filters():
    return jsonify(query_service.filter_options())


@bp.get("/meta")
def meta():
    info = {"total": 0, "competencia": None, "versao_id": None, "empty": True}
    with db.connection() as conn:
        if db.table_exists(conn, "procedimento_flat"):
            info["total"] = conn.execute(
                "SELECT COUNT(*) c FROM procedimento_flat").fetchone()["c"]
            info["empty"] = info["total"] == 0
        v = conn.execute(
            "SELECT id, competencia FROM app_versoes WHERE is_atual = 1 "
            "ORDER BY id DESC LIMIT 1").fetchone()
        if v:
            info["competencia"] = v["competencia"]
            info["versao_id"] = v["id"]
    return jsonify(info)


# --------------------------------------------------------------------------- #
# Favoritos
# --------------------------------------------------------------------------- #
@bp.get("/favoritos")
def fav_list():
    with db.connection() as conn:
        if db.table_exists(conn, "procedimento_flat"):
            rows = conn.execute(
                "SELECT f.co_procedimento, pf.no_procedimento, pf.vl_total "
                "FROM app_favoritos f "
                "LEFT JOIN procedimento_flat pf ON pf.co_procedimento = f.co_procedimento "
                "ORDER BY f.criado_em DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT co_procedimento, NULL AS no_procedimento, NULL AS vl_total "
                "FROM app_favoritos ORDER BY criado_em DESC"
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/favoritos")
def fav_add():
    code = (request.json or {}).get("co_procedimento", "").strip()
    if not code:
        return jsonify({"error": "co_procedimento obrigatório"}), 400
    with db.connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO app_favoritos (co_procedimento) VALUES (?)", (code,))
    return jsonify({"ok": True})


@bp.delete("/favoritos/<code>")
def fav_del(code: str):
    with db.connection() as conn:
        conn.execute("DELETE FROM app_favoritos WHERE co_procedimento = ?", (code,))
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Histórico de buscas
# --------------------------------------------------------------------------- #
@bp.get("/historico")
def historico():
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT termo, filtros, buscado_em FROM app_historico_busca "
            "ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# --------------------------------------------------------------------------- #
# Versões e comparação
# --------------------------------------------------------------------------- #
@bp.get("/versoes")
def versoes():
    return jsonify(compare_service.list_versions())


@bp.get("/compare")
def compare():
    a = request.args.get("a", type=int)
    b = request.args.get("b", type=int)
    if not a or not b:
        return jsonify({"error": "informe a e b (ids de versão)"}), 400
    return jsonify(compare_service.compare(a, b))


# --------------------------------------------------------------------------- #
# Relatórios
# --------------------------------------------------------------------------- #
@bp.get("/relatorio/<name>")
def relatorio(name: str):
    try:
        return jsonify(report_service.run(name))
    except KeyError:
        return jsonify({"error": "relatório desconhecido"}), 404


@bp.get("/relatorios")
def relatorios():
    return jsonify(sorted(report_service.REPORTS.keys()))


# --------------------------------------------------------------------------- #
# Exportação (respeita busca + filtros da consulta)
# --------------------------------------------------------------------------- #
EXPORT_COLUMNS = [
    "co_procedimento", "no_procedimento", "no_grupo", "no_sub_grupo",
    "no_forma_organizacao", "complexidade", "sexo", "no_financiamento",
    "vl_sh", "vl_sa", "vl_sp", "vl_total",
]


@bp.get("/export")
def export():
    fmt = request.args.get("fmt", "xlsx")
    source = request.args.get("source", "search")  # search | relatorio
    if source == "relatorio":
        rep = report_service.run(request.args.get("name", "lista_completa"))
        columns, rows, title = rep["columns"], rep["rows"], rep["title"]
        prefix = f"relatorio_{request.args.get('name','')}"
    else:
        term = request.args.get("q", "").strip()
        filters = _filters_from_request()
        codes = query_service.search_all_codes(term, filters)
        rows = []
        if codes:
            with db.connection() as conn:
                qs = ",".join("?" for _ in codes)
                rows = [dict(r) for r in conn.execute(
                    f"SELECT * FROM procedimento_flat WHERE co_procedimento IN ({qs}) "
                    f"ORDER BY co_procedimento", codes).fetchall()]
        columns, title, prefix = EXPORT_COLUMNS, "Consulta SIGTAP", "consulta_sigtap"

    try:
        path = exporters.export(fmt, columns, rows, prefix=prefix, title=title)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return send_file(path, as_attachment=True, download_name=path.name)


# --------------------------------------------------------------------------- #
# Competências: exportar qualquer mês (ZIP) para planilha, sem tocar na base
# --------------------------------------------------------------------------- #
@bp.get("/competencias")
def competencias():
    return jsonify({
        "pasta": str(config.COMPETENCIAS_DIR),
        "itens": competencia_service.list_zips(),
    })


@bp.get("/competencias/export")
def competencias_export():
    filename = request.args.get("file", "").strip()
    fmt = request.args.get("fmt", "xlsx")
    if not filename:
        return jsonify({"error": "informe o arquivo (file)"}), 400
    try:
        path = competencia_service.export_by_filename(filename, fmt)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.post("/competencias/export-upload")
def competencias_export_upload():
    """Exporta um ZIP enviado pelo usuário (não precisa estar numa pasta)."""
    fmt = request.form.get("fmt", "xlsx")
    if "file" not in request.files:
        return jsonify({"error": "Envie o arquivo ZIP no campo 'file'"}), 400
    up = request.files["file"]
    dest = Path(config.EXTRACT_DIR) / up.filename
    up.save(dest)
    try:
        path = competencia_service.export_zip(dest, fmt)
    finally:
        Path(dest).unlink(missing_ok=True)
    return send_file(path, as_attachment=True, download_name=path.name)


# --------------------------------------------------------------------------- #
# Atualização da base
# --------------------------------------------------------------------------- #
@bp.post("/atualizar")
def atualizar():
    from backend.app import run_update, UPDATE_JOB
    if UPDATE_JOB["running"]:
        return jsonify({"error": "Atualização já em andamento"}), 409
    run_update()
    return jsonify({"ok": True, "message": "Atualização iniciada"})


@bp.post("/importar")
def importar():
    """Importação manual do ZIP oficial (fallback ao download automático)."""
    from backend.app import run_update, UPDATE_JOB
    if UPDATE_JOB["running"]:
        return jsonify({"error": "Atualização já em andamento"}), 409
    if "file" not in request.files:
        return jsonify({"error": "Envie o arquivo ZIP no campo 'file'"}), 400
    up = request.files["file"]
    dest = Path(config.DOWNLOAD_DIR) / up.filename
    up.save(dest)
    run_update(source_zip=str(dest))
    return jsonify({"ok": True, "message": f"Importando {up.filename}"})


@bp.get("/status")
def status():
    from backend.app import UPDATE_JOB
    return jsonify({
        "running": UPDATE_JOB["running"],
        "log": UPDATE_JOB["log"][-100:],
        "result": UPDATE_JOB["result"],
        "error": UPDATE_JOB["error"],
    })
