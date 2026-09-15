# Contribuindo

Obrigado por contribuir com o Easy SINAPI ETL.

Antes de abrir um PR grande, leia o [ROADMAP.md](ROADMAP.md) e abra uma issue
para alinhar o âmbito. Ao participar, você concorda com o
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Caminhos de contribuição (do mais simples ao mais profundo)

| Tipo | Exemplos | Como |
|------|----------|------|
| **Docs** | README, exemplos, typos | PR direto e pequeno |
| **Bugs** | falha de parse, ZIP, Supabase | Issue com passos + PR se possível |
| **Features** | novo formato, UX desktop | Issue primeiro → discussão → PR |
| **Testes / CI** | fixtures, smoke | Issue ou PR alinhado ao roadmap |

## Como começar

1. Faça fork e clone.
2. Ambiente Python:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. (Opcional) `.env.example` → `.env` para testar Supabase.
4. (Opcional) Desktop: `cd desktop && yarn && yarn tauri dev`.
5. Crie um branch: `git checkout -b fix/descricao-curta` ou `feat/...`.

## Boas práticas

- Mudanças pequenas e focadas; um problema por PR.
- Não faça commit de `.env`, `.venv/`, `data/` ou artefatos de build.
- Mantenha o CLI (`main.py`) utilizável **sem** o app desktop.
- No PR: *porquê*, como testar, e referência à issue se existir.
- Atualize [CHANGELOG.md](CHANGELOG.md) em `[Unreleased]` quando a mudança for relevante para utilizadores.

## Testes

Sem download (Excel de exemplo na pasta indicada no script):

```bash
python3 test_etl.py
```

Smoke do CLI (dados reais da Caixa):

```bash
python3 main.py --latest --formats json
```

## Segurança

Não abra issue pública para vulnerabilidades. Siga [SECURITY.md](SECURITY.md).

## Idioma

Issues e PRs em **português** ou **inglês**.
