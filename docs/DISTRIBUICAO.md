# Distribuição open source (checklist)

Guia interno alinhado à estratégia: **comunidade e confiança primeiro; monetização depois**.
Não é obrigatório versionar este ficheiro a longo prazo — serve de checklist no lançamento.

## Antes do anúncio público

- [x] Remote GitHub: https://github.com/EduardoVilar23/SINAPI-Easy-ETL
- [ ] `git push -u origin main` (após commit do conteúdo OSS)
- [ ] About (≤350 caracteres) e Topics do README aplicados na página do repositório
- [ ] LICENSE MIT visível; Security Advisories ativos
- [ ] Tag `v0.1.0` + entrada no CHANGELOG
- [ ] Smoke: `python3 main.py --latest --formats json` documentado

## Canais (coordenar, não dispersar)

| Canal | Quando | Nota |
|-------|--------|------|
| GitHub (README + Topics) | Sempre | Hub principal de descoberta |
| DevHunt | Após release estável | Diretório focado em dev tools; submissão gratuita |
| Awesome lists | Após README claro + uso real | Backlinks e descoberta; PR com descrição objetiva |
| HN / Reddit / Dev.to | Lançamento coordenado | Terça–quarta de manhã (US Pacific) costuma performar melhor |
| Build in public | Contínuo | Progresso, métricas, falhas — atrai early adopters |

Stars sem história clara são vaidade: valor no README > volume de canais.

## Modelo de negócio (rascunho)

1. **Agora:** OSS self-host (MIT) = distribuição e confiança.  
2. **Depois:** managed service (API/dados atualizados) e/ou suporte.  
3. **Só se necessário:** open core (SSO, multi-tenant, auditoria) sem retirar o ETL local.

Empresas compram mitigação de risco (SLA, suporte, segurança), não só código.

## Metadados no GitHub

About e Topics: ver secção final do README. URLs de issues já apontam para `EduardoVilar23/SINAPI-Easy-ETL`.
