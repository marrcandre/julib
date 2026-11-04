# Entrega inicial — 04/11/2026

## Implementado e verificado localmente

- Backend Django/Ninja, PostgreSQL e Admin/Swagger com controle de acesso.
- Biblioteca/participantes, catálogo/edições/exemplares, tags, locais e operação em lote.
- Pessoas, empréstimos/devoluções/perdas e preservação de histórico.
- Busca Google Books/Open Library, assinatura/verificação de mídia, importação Goodreads idempotente e consulta por link revogável.
- Interface Vue/TypeScript/PrimeVue, tipos gerados por OpenAPI, paleta Siloé, temas e PWA online.
- README, MIT, contribuição, operação, workflows CI/deploy e template privado de backup.
- Revisão independente apontou três problemas relevantes (imutabilidade da biblioteca no Admin, repetição segura de cadastro após perda de resposta e ISBN Excel vazio); corrigidos com testes reproduzindo cada caso.

Validação: pytest no PostgreSQL, Vitest, Playwright contra API real, Ruff, mypy, vue-tsc/build, check/migrações Django. Backup cifrado de banco sintético restaurado e contagens conferidas. Ver o relatório final para a contagem mais recente.

## Infraestrutura preparada

- Código: https://github.com/marrcandre/julib (público).
- Operação: https://github.com/marrcandre/julib-backups (privado).
- Supabase: projeto Julib, organização IFC, região sa-east-1, criado com cotação mensal zero e status ACTIVE_HEALTHY. Ref kzdirwuopppjjnoxyavr.
- E-mails de login recebidos e armazenados somente em .env ignorado, sem publicar a conta da Juliana.

## Ainda depende de configuração externa

- Connection strings/credenciais Supabase de runtime, migração e backup; migrações reais e proteção da Data API.
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
