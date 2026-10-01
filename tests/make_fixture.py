"""Gera um ZIP sintético no formato SIGTAP para testes de ponta a ponta."""
import zipfile
from pathlib import Path

OUT = Path(__file__).parent / "fixture_sigtap.zip"


def fw(*parts):
    """Monta linha de largura fixa: parts = [(valor, tamanho), ...]."""
    return "".join(str(v)[:n].ljust(n) for v, n in parts)


def layout(fields):
    """fields = [(nome, tamanho)]; gera texto de layout com inicio/fim."""
    lines, pos = [], 1
    for name, size in fields:
        fim = pos + size - 1
        lines.append(f"{name.ljust(40)} {size:>6} {pos:>6} {fim:>6} VARCHAR2")
        pos = fim + 1
    return "\n".join(lines) + "\n"


FILES = {}

# tb_procedimento
proc_fields = [("CO_PROCEDIMENTO", 10), ("NO_PROCEDIMENTO", 250),
               ("TP_COMPLEXIDADE", 1), ("TP_SEXO", 1),
               ("VL_SH", 10), ("VL_SA", 10), ("VL_SP", 10),
               ("CO_FINANCIAMENTO", 2), ("DT_COMPETENCIA", 6)]
procs = [
    ("0301010010", "CONSULTA MEDICA EM ATENCAO BASICA", "1", "I", 0, 0, 1000, "06", "202406"),
    ("0209010037", "ENDOSCOPIA DIGESTIVA ALTA", "2", "I", 5000, 0, 3500, "04", "202406"),
    ("0209010045", "ENDOSCOPIA DIGESTIVA BAIXA (COLONOSCOPIA)", "2", "I", 8000, 0, 4200, "04", "202406"),
    ("0409060186", "CIRURGIA CARDIACA COM CEC", "3", "I", 250000, 0, 80000, "04", "202406"),
]
FILES["tb_procedimento.txt"] = "\n".join(
    fw((c, 10), (n, 250), (cx, 1), (sx, 1),
       (f"{sh:010d}", 10), (f"{sa:010d}", 10), (f"{sp:010d}", 10), (fin, 2), (dt, 6))
    for c, n, cx, sx, sh, sa, sp, fin, dt in procs) + "\n"
FILES["tb_procedimento_layout.txt"] = layout(proc_fields)

# tb_grupo
FILES["tb_grupo.txt"] = "\n".join(fw((c, 2), (n, 100)) for c, n in
    [("03", "PROCEDIMENTOS CLINICOS"), ("02", "PROCEDIMENTOS COM FINALIDADE DIAGNOSTICA"),
     ("04", "PROCEDIMENTOS CIRURGICOS")]) + "\n"
FILES["tb_grupo_layout.txt"] = layout([("CO_GRUPO", 2), ("NO_GRUPO", 100)])

# tb_sub_grupo
FILES["tb_sub_grupo.txt"] = "\n".join(fw((g, 2), (s, 2), (n, 100)) for g, s, n in
    [("03", "01", "CONSULTAS / ATENDIMENTOS"), ("02", "09", "DIAGNOSTICO POR ENDOSCOPIA"),
     ("04", "09", "CIRURGIA CARDIOVASCULAR")]) + "\n"
FILES["tb_sub_grupo_layout.txt"] = layout([("CO_GRUPO", 2), ("CO_SUB_GRUPO", 2), ("NO_SUB_GRUPO", 100)])

# tb_forma_organizacao
FILES["tb_forma_organizacao.txt"] = "\n".join(fw((g, 2), (s, 2), (f, 2), (n, 100)) for g, s, f, n in
    [("03", "01", "01", "CONSULTA"), ("02", "09", "01", "ENDOSCOPIA DIGESTIVA"),
     ("04", "09", "06", "CIRURGIA CARDIACA")]) + "\n"
FILES["tb_forma_organizacao_layout.txt"] = layout(
    [("CO_GRUPO", 2), ("CO_SUB_GRUPO", 2), ("CO_FORMA_ORGANIZACAO", 2), ("NO_FORMA_ORGANIZACAO", 100)])

# tb_financiamento
FILES["tb_financiamento.txt"] = "\n".join(fw((c, 2), (n, 100)) for c, n in
    [("04", "FAEC"), ("06", "ATENCAO BASICA (PAB)")]) + "\n"
FILES["tb_financiamento_layout.txt"] = layout([("CO_FINANCIAMENTO", 2), ("NO_FINANCIAMENTO", 100)])

# tb_descricao
FILES["tb_descricao.txt"] = "\n".join(fw((c, 10), (d, 300)) for c, d in
    [("0209010037", "Exame endoscopico do trato digestivo alto (esofago, estomago e duodeno)."),
     ("0209010045", "Exame endoscopico do colon (colonoscopia) com possibilidade de biopsia.")]) + "\n"
FILES["tb_descricao_layout.txt"] = layout([("CO_PROCEDIMENTO", 10), ("DE_PROCEDIMENTO", 300)])

# tb_cid + rl_procedimento_cid
FILES["tb_cid.txt"] = "\n".join(fw((c, 4), (n, 100)) for c, n in
    [("K297", "Gastrite nao especificada"), ("K638", "Outras doencas do intestino")]) + "\n"
FILES["tb_cid_layout.txt"] = layout([("CO_CID", 4), ("NO_CID", 100)])
FILES["rl_procedimento_cid.txt"] = "\n".join(fw((p, 10), (c, 4), (s, 1)) for p, c, s in
    [("0209010037", "K297", "S"), ("0209010045", "K638", "S")]) + "\n"
FILES["rl_procedimento_cid_layout.txt"] = layout(
    [("CO_PROCEDIMENTO", 10), ("CO_CID", 4), ("ST_PRINCIPAL", 1)])


def build():
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in FILES.items():
            zf.writestr(name, content.encode("latin-1"))
    print("Fixture criado:", OUT)
    return OUT


if __name__ == "__main__":
    build()
