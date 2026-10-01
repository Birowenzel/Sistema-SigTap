"""
Parser dos arquivos de layout da SIGTAP.

O pacote oficial do DATASUS traz, para cada arquivo de dados `XXXX.txt`, um
arquivo `XXXX_layout.txt` que descreve as colunas. O formato real é **CSV**,
com uma linha de cabeçalho:

    Coluna,Tamanho,Inicio,Fim,Tipo
    CO_PROCEDIMENTO,10,1,10,VARCHAR2
    NO_PROCEDIMENTO,250,11,260,VARCHAR2
    VL_SH,12,283,294,NUMBER
    ...

O arquivo de dados em si é de largura fixa (latin-1). Este módulo lê o layout e
devolve a estrutura para (a) criar a tabela e (b) recortar cada linha por
posição fixa. Também aceita, como fallback, o formato antigo separado por
espaços.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import config

# Fallback: formato antigo separado por espaços (name size inicio fim tipo)
_SPACE_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?P<size>\d+)\s+"
    r"(?P<inicio>\d+)\s+"
    r"(?P<fim>\d+)\s+"
    r"(?P<tipo>[A-Za-z0-9_]+)"
)


@dataclass(frozen=True)
class Field:
    name: str          # nome da coluna (minúsculo)
    inicio: int        # posição inicial 1-based
    fim: int           # posição final 1-based (inclusiva)
    tipo: str          # VARCHAR2 / NUMBER / CHAR / DATE ...

    @property
    def slice(self) -> slice:
        return slice(self.inicio - 1, self.fim)

    @property
    def is_numeric(self) -> bool:
        return self.tipo.upper().startswith(("NUM", "INT", "DEC", "MONEY"))

    @property
    def sql_type(self) -> str:
        # Guardamos tudo como TEXT para preservar zeros à esquerda dos códigos;
        # os valores monetários são convertidos no build do flat.
        return "TEXT"


def _parse_csv_line(parts: list[str]) -> Field | None:
    """Interpreta uma linha CSV do layout: Coluna,Tamanho,Inicio,Fim,Tipo."""
    if len(parts) < 4:
        return None
    name = parts[0].strip()
    inicio_s, fim_s = parts[2].strip(), parts[3].strip()
    if not name or not inicio_s.isdigit() or not fim_s.isdigit():
        return None  # cabeçalho ou linha inválida
    tipo = parts[4].strip() if len(parts) > 4 else "VARCHAR2"
    return Field(name=name.lower(), inicio=int(inicio_s), fim=int(fim_s), tipo=tipo)


def parse_layout(layout_path: Path) -> list[Field]:
    """Lê um arquivo *_layout.txt e devolve a lista ordenada de campos."""
    fields: list[Field] = []
    text = layout_path.read_text(encoding=config.SIGTAP_ENCODING, errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Formato oficial: CSV (também aceita ';' como separador)
        if "," in line or ";" in line:
            sep = "," if "," in line else ";"
            fld = _parse_csv_line(line.split(sep))
            if fld:
                fields.append(fld)
            continue

        # Fallback: separado por espaços
        m = _SPACE_RE.match(line)
        if m:
            fields.append(Field(
                name=m.group("name").strip().lower(),
                inicio=int(m.group("inicio")),
                fim=int(m.group("fim")),
                tipo=m.group("tipo").strip(),
            ))

    if not fields:
        raise ValueError(f"Layout sem colunas reconhecidas: {layout_path.name}")
    return fields


def find_layout_for(data_file: Path) -> Path | None:
    """Dado `tb_procedimento.txt`, encontra `tb_procedimento_layout.txt`."""
    stem = data_file.stem
    candidate = data_file.with_name(f"{stem}_layout.txt")
    if candidate.exists():
        return candidate
    # Alguns pacotes usam a pasta 'Layout' à parte
    alt = data_file.parent / "Layout" / f"{stem}_layout.txt"
    return alt if alt.exists() else None
