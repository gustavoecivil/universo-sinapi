# Easy SINAPI ETL

**ETL open source para baixar, transformar e exportar dados públicos do SINAPI (Caixa) em JSON, CSV, Parquet ou XLSX — com carga opcional no Supabase e app desktop Tauri.**

Use quando precisa de insumos e composições SINAPI atualizados sem planilhar ZIP/Excel à mão: engenharia de custos, orçamentação, BI e APIs internas.

[Requisitos](#requisitos) · [Instalação rápida](#instalação-rápida) · [CLI](#uso--linha-de-comando) · [Desktop](#interface-desktop-tauri--venv) · [Supabase](#carregar-no-supabase) · [Contribuir](#contribuindo) · [Roadmap](ROADMAP.md)

> **Aviso:** este projeto **não é afiliado** à Caixa Econômica Federal nem ao SINAPI. Os dados vêm da [fonte pública oficial](https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais/). O uso dos dados e a conformidade com termos da Caixa são responsabilidade de quem executa o software.

## O que este projeto faz

1. **Download** do ZIP mensal do SINAPI  
2. **Extração** do arquivo `SINAPI_Referência`  
3. **Transformação** das abas ISD, ICD, CSD, CCD e Analítico  
4. **Exportação** para JSON, CSV, Parquet e/ou XLSX  
5. **Carga opcional** no PostgreSQL via Supabase (schema `public` por padrão)

### Dados processados

Somente o ficheiro **SINAPI_Referência**, abas:

| Aba | Conteúdo |
|-----|----------|
| **ISD** | Insumos sem desoneração |
| **ICD** | Insumos com desoneração |
| **CSD** | Composições sem desoneração |
| **CCD** | Composições com desoneração |
| **Analítico** | Insumos de cada composição |

## Instalação rápida

```bash
git clone https://github.com/EduardoVilar23/SINAPI-Easy-ETL.git
cd SINAPI-Easy-ETL

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python3 main.py --latest           # processa o ZIP mais recente → data/processed/
```

Saída padrão: `json` + `csv` em `data/processed/<AAAA-MM>/`.

Windows (instalar Python): [INSTALACAO.md](INSTALACAO.md).

### Supabase (opcional)

```bash
cp .env.example .env
# edite SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY e, se preciso, SUPABASE_SCHEMA
# aplique structure.sql no SQL Editor do projeto

python3 main.py --latest --supabase
```

Sem `.env`, o ETL gera apenas ficheiros locais.

## Requisitos

- **Python** 3.10+ (3.11/3.12 recomendados)
- Internet para download no site da Caixa
- Desktop (opcional): Node.js, Yarn, Rust ([pré-requisitos Tauri](https://v2.tauri.app/start/prerequisites/))

### Dependências principais

| Pacote | Uso |
|--------|-----|
| `pandas`, `openpyxl`, `pyarrow` | Excel, CSV, JSON, Parquet, XLSX |
| `requests` | Download dos ZIPs |
| `supabase`, `python-dotenv` | Carga opcional e `.env` |
| `flask`, `flask-cors` | Nas dependências; não há app HTTP na raiz deste repositório |

## Estrutura do projeto

```
SINAPI-Easy-ETL/
├── src/                 # download, extract, transform, load, supabase, etl
├── data/                # runtime (ignorado pelo Git)
├── desktop/             # app Tauri opcional
├── main.py              # CLI
├── cleanup_reference.py # remove uma referência do Supabase
├── structure.sql        # DDL das tabelas SINAPI (schema public)
├── .env.example
├── docs/DISTRIBUICAO.md # checklist de lançamento / canais
├── ROADMAP.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE              # MIT
```

## Interface desktop (Tauri + `.venv`)

A pasta `desktop/` executa o ETL com o Python do `.venv` na raiz.

```bash
# 1) .venv na raiz (secção Instalação rápida)
cd desktop && yarn
yarn tauri dev          # use sempre este comando (não só yarn dev)
```

Na UI: referência (mês atual / mais recente / ano-mês), formatos de saída, carga Supabase e log em tempo real.

Build: `yarn tauri build` → `desktop/src-tauri/target/release/bundle/`.  
Detalhes: [desktop/README.md](desktop/README.md).

## Uso — linha de comando

```bash
python3 main.py                              # mês corrente
python3 main.py --year 2025 --month 12
python3 main.py --current
python3 main.py --latest
python3 main.py --year 2025 --month 12 --formats json csv parquet xlsx
python3 main.py --latest --supabase
```

Formatos: `json`, `csv`, `parquet`, `xlsx` (padrão: `json` `csv`).

### Carregar no Supabase

Com RLS ativo, use **service role** só em servidor/scripts locais — nunca no frontend. Modelo: [`.env.example`](.env.example).

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sua-service-role-secret
SUPABASE_SCHEMA=public
```

`SUPABASE_SCHEMA` define o schema PostgreSQL usado pelo loader e pelo `cleanup_reference.py`. O padrão é `public` (igual ao [`structure.sql`](structure.sql)). Se omitir a variável, o código também assume `public`. Só mude se as tabelas estiverem noutro schema (ex.: `SUPABASE_SCHEMA=sinapi_data`).

Aplique [`structure.sql`](structure.sql) antes da primeira carga. Documentação de chaves: [API Settings](https://app.supabase.com/project/_/settings/api).

`SupabaseLoader.load_from_processed_files` lê os JSON em `data/processed/<referencia>/`. Remover uma referência (irreversível):

```bash
python3 cleanup_reference.py 2026-02
```

## API Python (mínimo)

```python
from src.etl import SINAPIETL

etl = SINAPIETL()
etl.run(2025, 12, output_formats=["json", "csv"])
etl.run_latest_available(["json", "csv"], load_to_supabase=True)
```

Mais exemplos: `example_usage.py`, `analyze_sinapi.py`, `test_etl.py`.

## Notas

- ZIP válido em `data/downloads` é **reutilizado** (cache).
- Dados processados: `data/processed/<AAAA-MM>/`, com colunas normalizadas e metadados (`referencia`, `arquivo_origem`, `aba` quando aplicável).
- Fonte: [Relatórios mensais SINAPI — Caixa](https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais/). Padrão: `SINAPI-YYYY-MM-formato-xlsx.zip`.

## Modelo open source

- **Licença MIT** — adoção máxima; o software (código e docs) é livre; os dados SINAPI pertencem às fontes oficiais.
- **Self-host gratuito** — CLI e desktop locais; você controla os ficheiros e o Postgres.
- Caminho comercial natural (sem fechar o core): serviço gerido (dados sempre atualizados + API) e suporte — ver [ROADMAP.md](ROADMAP.md).

## Contribuindo

Leia [CONTRIBUTING.md](CONTRIBUTING.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).  
Vulnerabilidades: [SECURITY.md](SECURITY.md).  
Plano público: [ROADMAP.md](ROADMAP.md) · alterações: [CHANGELOG.md](CHANGELOG.md).

## Licença

[MIT](LICENSE). Este repositório licencia apenas o **software**, não os dados do SINAPI.

## Metadados sugeridos no GitHub (About)

Quando o repositório estiver no GitHub, configure:

| Campo | Sugestão |
|-------|----------|
| **About** | ETL open source do SINAPI (Caixa): download, transformação e exportação JSON/CSV/Parquet/XLSX, com Supabase opcional e app desktop. |
| **Topics** | `sinapi`, `etl`, `caixa`, `construcao-civil`, `orcamento`, `pandas`, `supabase`, `python`, `tauri`, `open-source`, `parquet`, `brasil` |
