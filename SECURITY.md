# Segurança

## Relatar uma vulnerabilidade

Se encontrar um problema de segurança (vazamento de credenciais, falha no tratamento de caminhos, etc.), **não** abra uma issue pública.

Envie um relatório privado via [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-managing-security-vulnerabilities/privately-reporting-a-security-vulnerability) do repositório (Security → Advisories → New draft advisory), ou contacte os mantenedores pelo canal do perfil do repositório.

Inclua:

- descrição do impacto;
- passos para reproduzir;
- versão / commit afetado;
- se a chave `SUPABASE_SERVICE_ROLE_KEY` (ou outra) pode ter sido exposta.

## Boas práticas para quem usa o projeto

- Nunca exponha `SUPABASE_SERVICE_ROLE_KEY` em apps cliente ou repositórios públicos.
- Use `.env` local (veja `.env.example`); o arquivo `.env` está no `.gitignore`.
- Rotacione chaves se suspeitar de exposição.
