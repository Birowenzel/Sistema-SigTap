# SIGTAP Local

Sistema interno para consulta **rápida e completa** da Tabela SIGTAP do SUS
(Sistema de Gerenciamento da Tabela de Procedimentos, Medicamentos, Órteses,
Próteses e Materiais Especiais).

Base 100% local, sempre atualizável a partir do DATASUS, com busca em **menos de
1 segundo**, exportações, comparação entre competências, favoritos, histórico e
relatórios gerenciais.

---

## 1. Requisitos

- **Python 3.11+** (testado em 3.14)
- Windows, Linux ou macOS

## 2. Instalação

```bash
cd sigtap
python -m pip install -r requirements.txt
```

## 3. Executar

```bash
python run.py
```

Acesse **http://127.0.0.1:5000** no navegador.

Na primeira execução a base está vazia. Clique em **⟳ Atualizar SIGTAP** para
baixar a competência mais recente do DATASUS, ou importe um ZIP oficial
manualmente (aba *Atualizar*).

### Linha de comando

```bash
python run.py update              # baixa a competência mais recente e importa
python run.py import ARQUIVO.zip  # importa um ZIP oficial já baixado
```

---

## 4. Funcionalidades

| Área | Recurso |
|------|---------|
| **Consulta** | Busca parcial por código, nome, descrição, grupo, subgrupo, forma de organização, complexidade, sexo, financiamento… (índice FTS5, sem acento). |
| **Detalhe** | Todos os campos da base + separação clara de **Valor Total / SH (Hospitalar) / SA (SADT) / SP (Profissional)**, financiamento/FAEC, e todas as tabelas relacionadas (CID, CBO, serviços, habilitações, compatibilidades, incrementos, regras, RENASES, leitos, detalhes…). |
| **Filtros** | Laterais, combináveis, com opções carregadas da base. |
| **Grade** | Paginação, ordenação por qualquer coluna, colunas configuráveis. |
| **Tema** | Claro/escuro (persistido). |
| **Exportação** | Excel (.xlsx), CSV e PDF — respeitando busca e filtros. |
| **Atualização** | Botão *Atualizar SIGTAP* (download automático) + import manual de ZIP; histórico de versões. |
| **Comparar** | Duas competências (ex.: Maio × Junho): adicionados, removidos, alterados, mudanças de valor. |
| **Favoritos** | Marque procedimentos de uso frequente. |
| **Histórico** | Últimas pesquisas, com repetição em um clique. |
| **Relatórios** | Mais pesquisados, lista completa, por grupo, produção por financiamento, honorários médicos, tabela hospitalar. |

---

## 5. Arquitetura / organização do código

```
sigtap/
├── run.py                  # ponto de entrada (web + CLI)
├── config.py               # caminhos e parâmetros
├── requirements.txt
│
├── backend/                # aplicação Flask + API
│   ├── app.py              #   fábrica do app + job de atualização (thread)
│   ├── api/routes.py       #   endpoints REST (JSON)
│   └── services/           #   regras de negócio
│       ├── query_service.py    (busca, filtros, paginação, ordenação)
│       ├── detail_service.py   (todos os campos de um procedimento)
│       ├── compare_service.py  (comparação entre versões)
│       └── report_service.py   (relatórios)
│
├── importer/               # importador SIGTAP
│   ├── downloader.py       #   download do DATASUS
│   ├── layout.py           #   parser dos arquivos *_layout.txt
│   ├── importer.py         #   ETL: extrai, carrega, monta flat + FTS
│   └── sigtap_meta.py      #   domínios, rótulos, filtros, seções
│
├── database/
│   └── db.py               # conexão SQLite (PRAGMAs) + tabelas da aplicação
│
├── exporters/
│   └── exporters.py        # Excel / CSV / PDF
│
├── utils/
│   └── formatting.py       # formatação (R$, competência)
│
├── frontend/               # interface (sem build step)
│   ├── templates/index.html
│   └── static/css/style.css, static/js/app.js
│
├── tests/make_fixture.py   # gera ZIP sintético para testes locais
└── data/                   # gerado em runtime (banco, downloads, exports)
    └── sigtap.db
```

### Banco de dados

- **SQLite** com `WAL` + cache de 64 MB e **FTS5** para busca textual.
- Importação **dinâmica**: cada arquivo de dados é criado a partir do seu
  arquivo de *layout* oficial, de modo que **todos os campos** da SIGTAP são
  carregados — inclusive campos novos que o DATASUS venha a acrescentar.
- Tabela desnormalizada `procedimento_flat` (com índices) garante consultas
  em < 1 s; relacionamentos preservados nas tabelas `tb_*` e `rl_*`.

**Migração para PostgreSQL:** reimplemente `database/db.py` com um driver
psycopg mantendo a mesma interface; o restante do código é agnóstico.

---

## 6. Origem dos dados

Tabela Unificada (SIGTAP) publicada pelo DATASUS:
`http://ftp2.datasus.gov.br/public/sistemas/tup/downloads/TabelasUnificadas/`

Caso o hospital bloqueie o acesso, baixe o ZIP manualmente e use a importação
manual na aba **Atualizar** (ou `python run.py import ARQUIVO.zip`).

## 7. Teste rápido (dados sintéticos)

```bash
python -c "from tests.make_fixture import build; from importer import importer; importer.import_zip(build(), '202406')"
python run.py
```
