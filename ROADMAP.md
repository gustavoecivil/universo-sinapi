# Roadmap

Plano público do Easy SINAPI ETL. Issues e PRs podem antecipar ou alterar prioridades — abra discussão se quiser influenciar a ordem.

## Princípios

1. **Core aberto** — download, transformação e exportação locais permanecem MIT e usáveis sem conta.
2. **Confiança primeiro** — documentação clara, segurança de credenciais e contribuição simples antes de monetização.
3. **Comunidade como distribuição** — bugs, exemplos e integrações dos utilizadores são o canal principal de crescimento.

## Agora (fundação)

- [x] CLI estável (`main.py`) com `--current`, `--latest`, formatos e `--supabase`
- [x] Schema `public` versionado (`structure.sql`; override com `SUPABASE_SCHEMA`)
- [x] App desktop Tauri opcional
- [x] CONTRIBUTING, SECURITY, LICENSE, CODE_OF_CONDUCT
- [ ] CI (lint/teste smoke sem credenciais)
- [ ] Releases versionadas (tags + CHANGELOG)
- [ ] Publicar repositório no GitHub com About + Topics (ver README)

## Próximo

- [ ] Testes automatizados do transformador com fixtures pequenas (sem download da Caixa)
- [ ] Documentar schema Supabase e exemplos de queries
- [ ] Melhorar UX do desktop (erros, cancelamento, progresso)
- [ ] Listas Awesome / DevHunt (após README e release estável)

## Depois (opcional / comercial)

Caminhos alinhados a **open source → serviço gerido**, sem remover o self-host:

| Camada | Ideia | Relação com o OSS |
|--------|--------|-------------------|
| **Managed / SaaS** | API ou base sempre atualizada com referências SINAPI | Self-host continua gratuito |
| **Suporte** | SLA, ajuda em deploy Supabase/on-prem | Código permanece aberto |
| **Open core (só se necessário)** | Multi-tenant, SSO, auditoria | Features enterprise; ETL base livre |

Comercialização será anunciada com antecedência e sem regressão do fluxo local documentado neste repositório.

## Fora de escopo (por agora)

- Espelhar todos os Excel do ZIP (só `SINAPI_Referência`)
- Substituir a fonte oficial da Caixa
- Expor `service_role` em cliente web
