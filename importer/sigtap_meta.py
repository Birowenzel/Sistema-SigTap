"""
Metadados de domínio da SIGTAP.

A importação em si é *dinâmica* (lê os arquivos de layout do próprio ZIP oficial),
portanto este módulo NÃO precisa listar todas as colunas. Ele guarda apenas:

  * DOMÍNIOS fixos (códigos de 1 dígito que não vêm em tabela: sexo, complexidade);
  * RÓTULOS amigáveis para colunas e tabelas;
  * a configuração dos FILTROS laterais;
  * os títulos das SEÇÕES na tela de detalhe do procedimento.

Assim o sistema continua funcionando mesmo que o DATASUS acrescente colunas novas.
"""
from __future__ import annotations

# Tabela principal e tabela de descrição textual
MAIN_TABLE = "tb_procedimento"
DESC_TABLE = "tb_descricao"

# --------------------------------------------------------------------------- #
# Domínios fixos (não vêm em arquivo próprio)
# --------------------------------------------------------------------------- #
DOMAIN_COMPLEXIDADE = {
    "0": "Não se aplica",
    "1": "Atenção Básica",
    "2": "Média Complexidade",
    "3": "Alta Complexidade",
}

DOMAIN_SEXO = {
    "M": "Masculino",
    "F": "Feminino",
    "N": "Não se aplica",
    "I": "Indiferente",
    "": "Indiferente",
}

# --------------------------------------------------------------------------- #
# Rótulos amigáveis de colunas (para telas e exportações)
# --------------------------------------------------------------------------- #
COLUMN_LABELS = {
    "co_procedimento": "Código",
    "no_procedimento": "Nome",
    "descricao": "Descrição",
    "co_grupo": "Cód. Grupo",
    "no_grupo": "Grupo",
    "co_sub_grupo": "Cód. Subgrupo",
    "no_sub_grupo": "Subgrupo",
    "co_forma_organizacao": "Cód. Forma Org.",
    "no_forma_organizacao": "Forma de Organização",
    "complexidade": "Complexidade",
    "sexo": "Sexo permitido",
    "qt_maxima_execucao": "Qtd. máxima",
    "qt_dias_permanencia": "Dias de permanência",
    "qt_tempo_permanencia": "Tempo de permanência",
    "qt_pontos": "Pontos",
    "vl_idade_minima": "Idade mínima",
    "vl_idade_maxima": "Idade máxima",
    "vl_sh": "Valor Hospitalar (SH)",
    "vl_sa": "Valor SADT/Ambulatorial (SA)",
    "vl_sp": "Valor Profissional (SP)",
    "vl_total": "Valor Total",
    "no_financiamento": "Tipo de Financiamento",
    "no_rubrica": "Rubrica",
    "instrumentos_registro": "Instrumento(s) de Registro",
    "modalidades": "Modalidade(s)",
    "dt_competencia": "Competência",
}

# --------------------------------------------------------------------------- #
# Filtros laterais.
#   column  -> coluna em procedimento_flat usada no WHERE
#   label   -> texto exibido
#   source  -> ('column', coluna_codigo, coluna_nome) para montar as opções
# --------------------------------------------------------------------------- #
FILTERS = [
    {"key": "co_grupo", "column": "co_grupo", "label": "Grupo",
     "opt_code": "co_grupo", "opt_name": "no_grupo"},
    {"key": "co_sub_grupo", "column": "co_sub_grupo", "label": "Subgrupo",
     "opt_code": "co_sub_grupo", "opt_name": "no_sub_grupo"},
    {"key": "co_forma_organizacao", "column": "co_forma_organizacao",
     "label": "Forma de Organização",
     "opt_code": "co_forma_organizacao", "opt_name": "no_forma_organizacao"},
    {"key": "complexidade", "column": "complexidade", "label": "Complexidade",
     "opt_code": "complexidade", "opt_name": "complexidade"},
    {"key": "sexo", "column": "sexo", "label": "Sexo permitido",
     "opt_code": "sexo", "opt_name": "sexo"},
    {"key": "no_financiamento", "column": "no_financiamento",
     "label": "Financiamento",
     "opt_code": "no_financiamento", "opt_name": "no_financiamento"},
]

# --------------------------------------------------------------------------- #
# Seções da tela de detalhe: tabelas de relacionamento e um título amigável.
# A ligação com o procedimento é detectada automaticamente pela coluna
# CO_PROCEDIMENTO; aqui só damos os nomes bonitos e a ordem.
# --------------------------------------------------------------------------- #
DETAIL_SECTIONS = [
    ("rl_procedimento_cid", "CID relacionados"),
    ("rl_procedimento_ocupacao", "CBO / Ocupações"),
    ("rl_procedimento_servico", "Serviço / Classificação"),
    ("rl_procedimento_habilitacao", "Habilitações"),
    ("rl_procedimento_registro", "Instrumentos de Registro"),
    ("rl_procedimento_modalidade", "Modalidades"),
    ("rl_procedimento_compativel", "Compatibilidades"),
    ("rl_procedimento_incremento", "Incrementos"),
    ("rl_procedimento_regra_cond", "Regras Condicionadas"),
    ("rl_procedimento_renases", "RENASES"),
    ("rl_procedimento_leito", "Tipos de Leito"),
    ("rl_procedimento_detalhe", "Detalhes / Exigências"),
    ("rl_procedimento_sia_sih", "Correlação SIA/SIH"),
    ("rl_procedimento_origem", "Procedimentos de Origem"),
]
