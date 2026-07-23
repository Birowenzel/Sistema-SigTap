# SIGTAP Local — Consulta da Tabela de Procedimentos do SUS

Sistema web para consulta **rápida, completa e offline** da Tabela SIGTAP do SUS (Sistema de Gerenciamento da Tabela de Procedimentos, Medicamentos, Órteses, Próteses e Materiais Especiais), publicada mensalmente pelo DATASUS.

A consulta oficial do DATASUS é lenta, depende de conexão externa e não permite comparar competências. Este sistema mantém uma **base local sempre atualizável**, com busca em **menos de 1 segundo**, exportações, comparação entre competências, favoritos, histórico e relatórios gerenciais.

O diferencial técnico está no importador: em vez de mapear manualmente os campos da SIGTAP, ele **lê os arquivos de layout oficiais** e monta o schema dinamicamente — de modo que campos novos acrescentados pelo DATASUS são carregados automaticamente, sem alteração de código.

---

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11+ (testado em 3.14) |
| Framework web | Flask 3.0.3 |
| Banco de dados | **SQLite** com **FTS5** (full-text search), modo WAL, cache de 64 MB |
| Download | requests 2.32.3 |
| Exportação Excel | openpyxl 3.1.5 |
| Exportação PDF | reportlab 4.2.2 |
| Frontend | HTML5 + CSS3 + JavaScript puro (**sem build step**) |
| Tipografia | Barlow (fontes WOFF2 locais — funciona sem internet) |

## Funcionalidades

| Área | Recurso |
|------|---------|
| **Consulta** | Busca parcial por código, nome, descrição, grupo, subgrupo, forma de organização, complexidade, sexo e financiamento — via índice **FTS5**, insensível a acentos |
| **Detalhe** | Todos os campos da base, com separação de **Valor Total / SH (Hospitalar) / SA (SADT) / SP (Profissional)**, financiamento/FAEC e todas as tabelas relacionadas: CID, CBO, serviços, habilitações, compatibilidades, incrementos, regras, RENASES, leitos e detalhes |
| **Filtros** | Laterais, combináveis, com opções carregadas dinamicamente da base |
| **Grade** | Paginação, ordenação por qualquer coluna e colunas configuráveis |
| **Tema** | Claro/escuro, persistido no navegador |
| **Exportação** | Excel (`.xlsx`), CSV e PDF — respeitando busca e filtros ativos |
| **Atualização** | Download automático do DATASUS + importação manual de ZIP; histórico de versões |
| **Comparação** | Duas competências lado a lado (ex.: Maio × Junho): procedimentos adicionados, removidos, alterados e mudanças de valor |
| **Favoritos** | Marcação de procedimentos de uso frequente |
| **Histórico** | Últimas pesquisas, repetíveis em um clique |
| **Relatórios** | Mais pesquisados, lista completa, por grupo, produção por financiamento, honorários médicos e tabela hospitalar |
| **CLI** | Atualização e importação por linha de comando, permitindo agendamento |

## Arquitetura

Arquitetura **em camadas com separação por responsabilidade**, organizada em pacotes Python independentes. O `run.py` é o único ponto de entrada e serve tanto o modo web quanto o CLI.

```
┌──────────────────────────────────────────────────────┐
│  frontend/   templates + static  (sem build step)    │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼──────────────────────────────┐
│  backend/api/routes.py      endpoints REST           │
├──────────────────────────────────────────────────────┤
│  backend/services/          regras de negócio        │
│    query_service · detail_service                    │
│    compare_service · report_service                  │
│    competencia_service                               │
├──────────────────────────────────────────────────────┤
│  database/db.py             conexão + PRAGMAs        │
└───────────────────────┬──────────────────────────────┘
                        │
                 ┌──────▼──────┐      ┌─────────────────┐
                 │  sigtap.db  │◄─────│  importer/  ETL │
                 │  SQLite+FTS5│      │  DATASUS → base │
                 └─────────────┘      └─────────────────┘
```

### Padrões aplicados

| Padrão | Onde aparece |
|--------|--------------|
| **Application Factory** | `backend/app.py` — fábrica do app Flask |
| **Service Layer** | `backend/services/` — regras de negócio isoladas das rotas |
| **Repository / DAL** | `database/db.py` — única porta de acesso ao banco; trocar SQLite por PostgreSQL exige reimplementar só este módulo |
| **Schema-driven ETL** | `importer/layout.py` lê os `*_layout.txt` oficiais e gera as tabelas dinamicamente |
| **Desnormalização para leitura** | `procedimento_flat` — tabela achatada e indexada garantindo consulta sub-segundo |
| **Background job** | Thread de atualização disparada pela interface, sem travar o servidor |
| **Strategy de exportação** | `exporters/exporters.py` — XLSX, CSV e PDF sob a mesma interface |

## Estrutura das Pastas

```
Sistema da Sigtap/
├── run.py                       # ponto de entrada (web + CLI)
├── config.py                    # caminhos e parâmetros
├── requirements.txt
├── .gitignore
│
├── backend/                     # aplicação Flask + API
│   ├── app.py                   #   fábrica do app + job de atualização
│   ├── api/routes.py            #   endpoints REST (JSON)
│   └── services/                #   regras de negócio
│       ├── query_service.py     #     busca, filtros, paginação, ordenação
│       ├── detail_service.py    #     todos os campos de um procedimento
│       ├── compare_service.py   #     comparação entre competências
│       ├── competencia_service.py
│       └── report_service.py    #     relatórios gerenciais
│
├── importer/                    # importador SIGTAP (ETL)
│   ├── downloader.py            #   download do FTP do DATASUS
│   ├── layout.py                #   parser dos arquivos *_layout.txt
│   ├── importer.py              #   extrai, carrega, monta flat + FTS
│   └── sigtap_meta.py           #   domínios, rótulos, filtros, seções
│
├── database/
│   └── db.py                    # conexão SQLite (PRAGMAs) + tabelas da app
│
├── exporters/
│   └── exporters.py             # Excel / CSV / PDF
│
├── utils/
│   └── formatting.py            # formatação (R$, competência)
│
├── frontend/                    # interface (sem build step)
│   ├── templates/index.html
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       ├── fonts/               # Barlow em WOFF2 (offline)
│       └── img/logo.png
│
├── tests/
│   └── make_fixture.py          # gera ZIP sintético para testes locais
│
└── data/                        # gerado em runtime (não versionar)
    ├── sigtap.db
    ├── downloads/
    ├── extract/
    └── exports/
```

## Como executar

### Pré-requisitos
- **Python 3.11 ou superior**
- Windows, Linux ou macOS

### Instalação

```bash
python -m pip install -r requirements.txt
```

### Modo web

```bash
python run.py
```

Acesse **http://127.0.0.1:5000**.

Na primeira execução a base está vazia. Clique em **⟳ Atualizar SIGTAP** para baixar a competência mais recente do DATASUS, ou importe um ZIP oficial manualmente na aba *Atualizar*.

### Modo linha de comando

```bash
python run.py update              # baixa a competência mais recente e importa
python run.py import ARQUIVO.zip  # importa um ZIP oficial já baixado
```

### Teste rápido com dados sintéticos

```bash
python -c "from tests.make_fixture import build; from importer import importer; importer.import_zip(build(), '202406')"
python run.py
```

## Configuração

Parâmetros centralizados em `config.py` (caminhos de dados, downloads e exports).

| Item | Padrão |
|------|--------|
| Porta HTTP | `5000` |
| Banco | `data/sigtap.db` |
| Downloads | `data/downloads/` |
| Extração | `data/extract/` |
| Exportações | `data/exports/` |

Este projeto **não requer credenciais** — consome apenas o FTP público do DATASUS. É, por isso, o projeto do portfólio mais pronto para publicação imediata.

## Banco de Dados

**SQLite** com as seguintes otimizações:

- `journal_mode = WAL` — permite leituras concorrentes durante a importação.
- Cache de **64 MB** via PRAGMA.
- **FTS5** para busca textual insensível a acento e a caixa.
- Tabela desnormalizada **`procedimento_flat`** com índices, garantindo consulta em menos de 1 segundo.
- Relacionamentos originais preservados nas tabelas `tb_*` (domínios) e `rl_*` (relacionamentos).

### Importação dinâmica

Cada arquivo de dados é criado a partir do seu arquivo de *layout* oficial (`*_layout.txt`), de modo que **todos os campos** da SIGTAP são carregados — inclusive campos novos que o DATASUS venha a acrescentar, **sem alteração de código**.

### Migração para PostgreSQL

Reimplemente `database/db.py` com um driver `psycopg` mantendo a mesma interface pública. O restante do código é agnóstico quanto ao SGBD.

## Origem dos dados

Tabela Unificada (SIGTAP) publicada pelo DATASUS:

```
http://ftp2.datasus.gov.br/public/sistemas/tup/downloads/TabelasUnificadas/
```

Caso a rede da instituição bloqueie o acesso ao FTP, baixe o ZIP manualmente e use a importação manual na aba **Atualizar** (ou `python run.py import ARQUIVO.zip`).


## Autor

**Paulo Emanuel Wenzel**
