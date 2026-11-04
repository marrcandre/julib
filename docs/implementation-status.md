# Entrega inicial — 04/11/2026

## Implementado e verificado localmente

- Backend Django/Ninja, PostgreSQL e Admin/Swagger com controle de acesso.
- Biblioteca/participantes, catálogo/edições/exemplares, tags, locais e operação em lote.
- Pessoas, empréstimos/devoluções/perdas e preservação de histórico.
- Busca Google Books/Open Library, assinatura/verificação de mídia, importação Goodreads idempotente e consulta por link revogável.
- Interface Vue/TypeScript/PrimeVue, tipos gerados por OpenAPI, paleta Siloé, temas e PWA online.
- README, MIT, contribuição, operação, workflows CI/deploy e template privado de backup.
- Revisão independente apontou três problemas relevantes (imutabilidade da biblioteca no Admin, repetição segura de cadastro após perda de resposta e ISBN Excel vazio); corrigidos com testes reproduzindo cada caso.

Validação: 25 testes pytest no PostgreSQL, 6 Vitest e 3 jornadas Playwright contra API real; Ruff, mypy, vue-tsc/build e check/migrações Django aprovados. Backup cifrado de banco sintético restaurado e contagens conferidas. Ver o relatório final para a contagem mais recente.

## Infraestrutura preparada

- Código: https://github.com/marrcandre/julib (público).
- Operação: https://github.com/marrcandre/julib-backups (privado).
- Supabase: projeto Julib, organização IFC, região sa-east-1, criado com cotação mensal zero e status ACTIVE_HEALTHY. Ref kzdirwuopppjjnoxyavr.
- E-mails de login recebidos e armazenados somente em .env ignorado, sem publicar a conta da Juliana.

CI remota aprovada em 04/11/2026 para o commit 0a2f8d7: execução https://github.com/marrcandre/julib/actions/runs/41890507217. PR inicial: https://github.com/marrcandre/julib/pull/1. O primeiro ajuste de CI corrigiu o quoting do healthcheck PostgreSQL no runner; o job completo, incluindo Playwright, passou depois da correção.

## Ainda depende de configuração externa

- Supabase: conexão real validada com TLS, 36 migrações aplicadas, biblioteca inicial sem dados de teste, role runtime julib_app limitada e 28 tabelas com RLS/grants verificados. Runtime e migração em .env privado; ainda falta configurar esses secrets em GitHub/Vercel e ativar o backup.
- Cliente OAuth Google e validação com as duas contas reais.
- Credenciais Cloudinary e upload/recuperação reais de mídia, incluindo medição de sete cópias nas cotas gratuitas.
- Projetos Vercel, segredos GitHub/Vercel e teste de cookies/redirects em origem única. Deploy fica desabilitado por DEPLOY_ENABLED até concluir pré-requisitos.
- Agenda de backup privado desabilitada até configurar banco/mídia e guardar chave privada de recuperação fora do GitHub.
- Câmera e instalação físicas no Poco F5/Samsung A34; os testes Chromium em desktop/móvel não substituem essa validação.

Snapshots de mídia completos têm limite de 50 MB por pacote. Se exceder, é necessário implementar/validar deduplicação ou outro destino privado gratuito antes da ativação; não há redução silenciosa da cobertura.

## Decisões de implementação

- Repositório novo inicializado na branch feat/julib-v1, sem checkout anterior para proteger; não foi criado outro worktree.
- Execução inline com revisão independente ao final, sem agentes implementadores por tarefa.
- PrimeVue na linha 4 MIT; fontes Inter locais; páginas carregadas sob demanda.
- Cadastro inicial usa uma operação transacional e chave idempotente, em vez de duas gravações independentes.
- Não foram identificados achados menores diferidos pelo revisor. Pendências externas são descritas acima e não são tratadas como serviços ativos.

## Integração Supabase — 04/11/2026

O usuário forneceu DATABASE_URL pelo .env. Conexões transaction e session pooler confirmadas no projeto correto. Corrigido o merge de OPTIONS no Django para preservar sslmode da URI, com regressão RED→GREEN. Conta administrativa preservada como MIGRATION_DATABASE_URL; DATABASE_URL passou à role de execução com senha própria, sem superuser/createrole/createdb/bypassrls. Nenhuma credencial publicada.

Migrações e bootstrap executados; 1 biblioteca e 0 livros. Segurança conferida por SQL e advisors: 28 tabelas com RLS, anon/authenticated sem SELECT e zero avisos.

## Desenvolvimento em Docker — 04/11/2026

Docker ativado pelo usuário. PostgreSQL 17 do Compose saudável em 127.0.0.1:5432, com volume persistente. Bancos julib (desenvolvimento) e julib_e2e (jornadas) preparados; pytest cria e remove test_julib. Migrações e biblioteca inicial locais aplicadas sem copiar dados do Supabase.

.env privado do Supabase preservado. .env.local privado sobrescreve apenas DEBUG e DSNs locais; exemplo versionado em .env.local.example. Os comandos make *-local selecionam o banco Docker mesmo com uma URL remota exportada no shell. Credenciais Google/Cloudinary continuam carregadas de .env quando disponíveis.

Validação no Docker: 28 testes backend, 6 frontend, 3 jornadas Playwright e build/tipos/checks aprovados.

## Preparação do OAuth Google local — 04/11/2026

Cliente Google fornecido pelo usuário no .env privado; entradas duplicadas vazias foram consolidadas sem publicar credenciais. Corrigido o proxy Vite para preservar a origem pública do navegador: o callback permanece na porta 5173 e é encaminhado ao Django na porta 8000. Teste HTTP reproduziu a falha antes da correção e passou depois.

Validação local: 28 testes backend, 6 frontend, 4 jornadas Playwright, Ruff/mypy, checks Django e build/tipos aprovados. A autenticação completa e a troca de código por token ainda dependem do primeiro login interativo com as contas autorizadas; nenhum consentimento foi automatizado.

## Correção CSRF no formulário de login — 04/11/2026

Reproduzido em Chromium o erro reportado: a política no-referrer do PrivacyMiddleware fazia a navegação POST do formulário enviar Origin: null. Ajustada para same-origin, preservando referências internas e omitindo referências externas. Proteção CSRF permanece ativa. Novo teste aciona o botão real de confirmação e verifica a origem enviada e o redirecionamento ao Google (destino externo simulado, sem autenticar usuários). O teste falhou antes do ajuste e passou depois; o teste HTTP de callback também passou.
