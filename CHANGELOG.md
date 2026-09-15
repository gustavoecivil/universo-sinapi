# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o versionamento pretende seguir [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Added

- Documentação de comunidade: `CODE_OF_CONDUCT.md`, `ROADMAP.md`, templates de issue/PR
- README reorganizado para descoberta (valor, quick start, metadados GitHub)

### Changed

- Schema padrão de carga Supabase: `public` (antes schema dedicado); opcional via `SUPABASE_SCHEMA`
- Refino de `CONTRIBUTING.md` com caminho de contribuição mais explícito

## [0.1.0] — 2026-09-15

### Added

- ETL CLI para SINAPI_Referência (ISD, ICD, CSD, CCD, Analítico)
- Exportação JSON, CSV, Parquet, XLSX
- Carga opcional no Supabase (schema `public`) e `cleanup_reference.py`
- App desktop Tauri opcional
- `LICENSE` (MIT), `SECURITY.md`, `.env.example`
