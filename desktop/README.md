# Easy SINAPI — Desktop

App Tauri (opcional) que executa o ETL Python (`main.py`) usando o `.venv` na raiz do repositório.

## Setup

Na raiz do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No app:

```bash
cd desktop
yarn
```

## Desenvolvimento

```bash
yarn tauri dev
```

Use `yarn tauri dev` (não só `yarn dev`). O Vite no browser não tem a API Tauri; o ETL e o log em tempo real só funcionam na janela nativa.

## Build

```bash
yarn tauri build
```

Artefatos em `src-tauri/target/release/bundle/`.
