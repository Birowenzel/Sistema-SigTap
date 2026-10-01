"""
Download da Tabela Unificada (SIGTAP) a partir do DATASUS.

O DATASUS publica os pacotes mensais em `ftp2.datasus.gov.br`. O acesso pode ser
feito por FTP (protocolo nativo) ou HTTP. Em redes hospitalares é comum o acesso
direto ser bloqueado pelo firewall, funcionando apenas via proxy corporativo —
por isso o downloader:

  * tenta VÁRIOS endereços candidatos (FTP e HTTP), em ordem;
  * respeita proxy (variáveis HTTP_PROXY/HTTPS_PROXY ou config.DATASUS_PROXY);
  * usa timeout curto por tentativa e agrega os erros numa mensagem clara.

Se nada funcionar (firewall total), a interface oferece a importação manual do
ZIP oficial, que é o caminho garantido.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from ftplib import FTP
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

# Nomes: TabelaUnificada_202406_v2406071.zip (novos) ou TabelaUnificada_200801.zip
# (antigos, sem sufixo de versão).
_ZIP_RE = re.compile(r"TabelaUnificada_(\d{6})(?:_v[\w]+)?\.zip", re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']?([^"\'>\s]+\.zip)', re.IGNORECASE)


@dataclass
class RemoteFile:
    filename: str
    competencia: str  # AAAAMM
    base_url: str     # diretório de origem (para montar a URL de download)


def _proxies() -> dict | None:
    proxy = getattr(config, "DATASUS_PROXY", None)
    return {"http": proxy, "https": proxy} if proxy else None


# --------------------------------------------------------------------------- #
# Listagem
# --------------------------------------------------------------------------- #
def _list_http(base: str) -> list[RemoteFile]:
    resp = requests.get(base, timeout=config.DATASUS_TIMEOUT, proxies=_proxies())
    resp.raise_for_status()
    out = {}
    for href in _HREF_RE.findall(resp.text):
        fname = href.split("/")[-1]
        m = _ZIP_RE.search(fname)
        if m:
            out[fname] = RemoteFile(fname, m.group(1), base)
    return list(out.values())


def _list_ftp(base: str) -> list[RemoteFile]:
    p = urlparse(base)
    ftp = FTP(p.hostname, timeout=config.DATASUS_TIMEOUT)
    ftp.login()  # anônimo
    try:
        ftp.cwd(p.path)
        names = ftp.nlst()
    finally:
        ftp.quit()
    out = {}
    for name in names:
        fname = name.split("/")[-1]
        m = _ZIP_RE.search(fname)
        if m:
            out[fname] = RemoteFile(fname, m.group(1), base)
    return list(out.values())


def list_remote_files(base: str) -> list[RemoteFile]:
    scheme = urlparse(base).scheme.lower()
    files = _list_ftp(base) if scheme == "ftp" else _list_http(base)
    return sorted(files, key=lambda f: (f.competencia, f.filename), reverse=True)


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def _download_http(remote: RemoteFile, dest: Path) -> None:
    url = remote.base_url.rstrip("/") + "/" + remote.filename
    with requests.get(url, stream=True, timeout=config.DATASUS_TIMEOUT,
                      proxies=_proxies()) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)


def _download_ftp(remote: RemoteFile, dest: Path) -> None:
    p = urlparse(remote.base_url)
    ftp = FTP(p.hostname, timeout=config.DATASUS_TIMEOUT)
    ftp.login()
    try:
        ftp.cwd(p.path)
        with open(dest, "wb") as fh:
            ftp.retrbinary(f"RETR {remote.filename}", fh.write)
    finally:
        ftp.quit()


def download_file(remote: RemoteFile, dest_dir: Path | None = None) -> Path:
    dest = Path(dest_dir or config.DOWNLOAD_DIR) / remote.filename
    if urlparse(remote.base_url).scheme.lower() == "ftp":
        _download_ftp(remote, dest)
    else:
        _download_http(remote, dest)
    return dest


# --------------------------------------------------------------------------- #
# Orquestração: tenta cada endereço candidato
# --------------------------------------------------------------------------- #
def download_latest(log=lambda *_: None) -> tuple[Path, str]:
    """Baixa a competência mais recente. Retorna (caminho_zip, competencia)."""
    errors = []
    for base in config.DATASUS_CANDIDATES:
        try:
            log(f"Tentando {base} …")
            files = list_remote_files(base)
            if not files:
                errors.append(f"{base}: nenhum ZIP encontrado")
                continue
            latest = files[0]
            log(f"Encontrado {latest.filename}. Baixando…")
            path = download_file(latest)
            return path, latest.competencia
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {type(exc).__name__} — {exc}")
            log(f"  falhou: {exc}")

    raise RuntimeError(
        "Não foi possível acessar o DATASUS automaticamente. Isto normalmente é "
        "bloqueio de firewall/proxy da rede hospitalar (o download manual pelo "
        "navegador funciona porque usa o proxy). Configure SIGTAP_PROXY com o "
        "proxy corporativo, ou use a importação manual do ZIP.\nDetalhes:\n  - "
        + "\n  - ".join(errors)
    )
