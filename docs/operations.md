# Operação do Julib

Operação ativa: aplicação publicada e integrações configuradas. O backup privado tem recuperação validada, mas a agenda automática está pausada enquanto GitHub Actions estiver desativado; backup não é condição para cada publicação. Consulte o histórico de implementação para as evidências e a [auditoria de requisitos](reviews/2026-11-05-requisitos-e-proximas-entregas.md) para pendências atuais.

## Configuração privada

Copie `.env.example` para `.env`; não publique esse arquivo. `ALLOWED_EMAILS` contém os dois e-mails verificados pelo Google; `ADMIN_EMAIL` é um deles. Apenas essa conta recebe staff/superuser para o Django Admin. Sessões continuam sujeitas à allowlist em cada chamada; remover um e-mail bloqueia a API imediatamente.

Use SECRET_KEY aleatória longa, DEBUG=false em produção, ALLOWED_HOSTS explícitos e CSRF_TRUSTED_ORIGINS com a origem pública HTTPS. O contato/PIX público do autor não determina o e-mail de login.

## PostgreSQL / Supabase

Local: `make db`, com PostgreSQL 17 na porta 5432 vinculada somente a 127.0.0.1 e volume persistente do Compose. `.env.local` contém apenas DSNs locais e DEBUG; `.env` preserva a conexão Supabase e as credenciais compartilhadas. Os alvos migrate-local, bootstrap-local, backend-local e check-local removem DSNs exportadas no shell antes de carregar os dois arquivos. O backend sem DATABASE_URL também usa a conexão local do Compose.

Bancos separados: julib para desenvolvimento, test_julib criado pelo pytest e julib_e2e para jornadas com dados fictícios. Use `make e2e-local` com servidores 8000/5173 parados. `docker compose stop db` para o serviço sem apagar o volume; `down -v` remove dados e não faz parte da rotina normal.

O PostgreSQL temporário antigo na porta 55432 foi usado na preparação inicial; o ambiente padrão passou ao Docker em 04/11/2026.

Produção: copie a connection string do painel Supabase; não derive o hostname. DATABASE_URL do runtime usa pooler transaction, prepared statements desabilitados e sem cursores persistentes de servidor. Migração e dump usam conexão direta ou session pooler compatível com a rede. Configure TLS conforme painel; não misture credenciais reais em CI de PRs.

**Antes de inserir dados reais:** desative a Data API se não for usada e remova grants de anon/authenticated nos schemas Django expostos; verifique RLS/revogação no painel/advisors. Django é o único caminho autorizado aos dados. Não crie policies públicas para fazer o frontend acessar tabelas. Configuração inicial do Julib verificada: 28 tabelas com RLS, grants de leitura de anon/authenticated ausentes e advisory de segurança vazio em 04/11/2026. Revalidar após novas migrações.

O projeto Julib foi provisionado em 04/11/2026. A connection string de runtime usa a role julib_app com DML e sem DDL; MIGRATION_DATABASE_URL preserva a conta administrativa no session pooler. Ambas estão apenas no .env privado e precisam ser configuradas como secrets/env nos serviços corretos. Não coloque a URL administrativa no runtime frontend/backend.

As tabelas Django usam RLS com policy explícita para a role confiável julib_app; isolamento entre bibliotecas continua no Django. anon/authenticated não têm grants e não têm policies. O comando `secure_database --role julib_app`, executado com a conta de migração, revoga grants públicos, protege tabelas atuais e defaults, e concede somente DML/uso de sequências ao backend. O workflow executa esse comando antes/depois das migrações. Não conceda BYPASSRLS ou CREATE à role de runtime.

Em novo projeto, provisione uma role julib_app com senha privada e sem privilégios administrativos antes do comando. Em recuperação, crie essa role antes de restaurar policies que a referenciem. Não reutilize senha de exemplos.

Após carregar .env, `make migrate` seleciona MIGRATION_DATABASE_URL quando presente. Execute bootstrap_library com allowlist configurada; a biblioteca já foi provisionada neste ambiente. A biblioteca precisa existir antes do primeiro login Google.

## Login Google

Crie um cliente OAuth Web no projeto Google. Configure a tela de consentimento e os usuários permitidos/testadores quando o app estiver em modo de testes. Credenciais ficam somente no Django, em GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET. Escopos: identidade básica/e-mail.

URI de retorno local usando o proxy: `http://127.0.0.1:5173/accounts/google/login/callback/`. Produção: `https://SEU_FRONTEND/accounts/google/login/callback/`. A origem pública deve estar nos hosts/CSRF Django. Defina APP_ORIGIN=https://julib.vercel.app no runtime de produção para o callback usar a interface atrás do proxy; mantenha vazio no desenvolvimento local. Não coloque o domínio do backend como callback se a sessão for utilizada pela origem frontend.

O link de entrada abre a confirmação OAuth do allauth. Somente e-mail verificado em allowlist é aceito; novos usuários são associados à biblioteca inicial no provisionamento OAuth, e contas já existentes mantêm suas memberships. Use `bootstrap_library` para provisionar memberships de usuários existentes da allowlist. A migração `0010` conserva as memberships existentes, atribui o papel administrativo às contas técnicas existentes e armazena a permissão explícita de criar bibliotecas. Essa capacidade fica no usuário; não é derivada do papel na biblioteca durante as chamadas da API. Valide o login e a permissão de criação com a conta administrativa e uma conta sem essa capacidade.

## Migração para múltiplas bibliotecas

As migrações `0010` e `0011` são aditivas. `0010` adiciona papel à membership e a permissão global de criação sem copiar nem alterar livros, empréstimos, IDs de biblioteca ou referências Cloudinary. A migração mantém admins legados (memberships de usuários `is_staff`) e deixa `can_create_libraries` falso; `bootstrap_library` concede essa capacidade à conta correspondente ao `ADMIN_EMAIL`. `0011` acrescenta chaves e FKs compostas para locais, exemplares, empréstimos e recibos de cadastro, além de triggers de integridade para tags e linhas de importação.

Esta `0010` ainda não foi publicada e foi corrigida diretamente. Um banco de desenvolvimento que já registrou a versão anterior da migração não executará o novo `RunPython` automaticamente; confira `can_create_libraries` nesse banco e, se for descartável, recrie-o para exercitar o histórico corrigido. Não use um banco de produção para esse procedimento.

Antes de aplicar `0011`, execute o preflight somente de leitura descrito abaixo. Ele confere também tags de livros e exemplares de linhas de importação; essas tabelas não armazenam uma coluna de biblioteca compartilhada e são protegidas por triggers. As constraints compostas são validadas na migração; os triggers protegem novas relações e mudanças posteriores, enquanto o preflight detecta relações antigas inconsistentes. Investigue e corrija qualquer divergência antes de repetir.

Publique backend e frontend juntos antes de criar uma segunda biblioteca. A API mantém compatibilidade para contas com uma única membership sem cabeçalho de contexto; contas com várias memberships precisam enviar `X-Library-ID`, que o backend valida a cada operação. A URL da interface determina esse cabeçalho por aba. Depois que houver mais de uma biblioteca, não faça rollback para uma versão anterior à Fase 1: ela ignora o cabeçalho e pode operar na primeira membership. Use correção para frente ou uma versão de rollback que suporte múltiplas bibliotecas.

## Cloudinary

Configure CLOUDINARY_URL ou CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET apenas no backend. O SDK prioriza as variáveis individuais quando CLOUDINARY_CLOUD_NAME está preenchida; use um único formato para evitar misturar contas. A API assina upload na pasta da biblioteca; frontend envia arquivo diretamente para Cloudinary e solicita vínculo ao livro. Servidor consulta a mídia para validar origem e tamanho final. Limite da aplicação: 5 MB e imagens JPEG/PNG/WebP; configure também os limites de upload disponíveis na conta para conter originais muito grandes. Segredos nunca vão ao cliente.

Capas das APIs externas permanecem como URLs da fonte. Respeite os termos de Google Books/Open Library e atribua a fonte quando necessário. Nada de scraping de Goodreads.

## Vercel e CI/CD

Produção atual: https://julib.vercel.app (frontend) e https://julib-api.vercel.app (backend), em plano Hobby. O banco é o Supabase Julib e as capas enviadas ficam no Cloudinary Free.

Dois projetos a partir do mesmo repositório: root directory backend e frontend. Não ativar auto deploy por push nem previews com acesso à produção. O workflow Deploy depende de CI bem-sucedida no mesmo commit da branch main e de DEPLOY_ENABLED=true.

Frontend: build `npm run build`, output `dist`. Gere rewrites com `BACKEND_ORIGIN=https://SEU_BACKEND uv run python scripts/configure_frontend.py` a partir da raiz. O arquivo frontend/vercel.json é gerado e ignorado. Backend: entrypoint config/wsgi.py e collectstatic; migrations são executadas separadamente no workflow. Teste a integração de cookies/redirects/Swagger no deploy.

Secrets no GitHub: VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_BACKEND_PROJECT_ID, VERCEL_FRONTEND_PROJECT_ID, MIGRATION_DATABASE_URL, DJANGO_SECRET_KEY. Variáveis: BACKEND_ORIGIN, APP_ORIGIN e DEPLOY_ENABLED. O workflow de publicação não solicita nem aguarda um backup por deploy. Mantenha o backup como rotina operacional independente e planeje a recuperação conforme o risco das mudanças no banco. Os envs de runtime (Google/Cloudinary/banco/allowlist etc.) ficam nos projetos Vercel. Crie o environment production com os controles desejados e serialização.

Antes de habilitar DEPLOY_ENABLED: CI remota verde, Google validado, Data API protegida, migrações revisadas como compatíveis e cotas verificadas. Não faça migrações destrutivas automaticamente. Backup e publicação são rotinas independentes; uma publicação comum não exige uma nova cópia. Para migrações com risco de perda de dados, defina e valide previamente uma estratégia de recuperação adequada ao impacto.

Falha de backend interrompe publicação do frontend. Rollback do código só com schema compatível; recuperação do banco é deliberada e precisa de destino revisado. O workflow não desfaz migrações automaticamente.

## Backup privado diário

Mantenha o código num repositório público e o workflow operacional em repositório privado. Copie ops/backup-workflow.yml.example para `.github/workflows/backup.yml` **somente no privado**. O job recusa repositório público. Agenda UTC 06:23 (03:23 em São Paulo), também com execução manual.

Gere chaves localmente:

```sh
uv run --project backend python scripts/backup.py keygen --private /CAMINHO_SEGURO/julib-private.pem --public /CAMINHO_SEGURO/julib-public.pem
```

Guarde a chave privada fora do GitHub e uma segunda cópia segura. A chave pública PEM entra no secret BACKUP_PUBLIC_KEY do repositório privado. Outros secrets: BACKUP_DATABASE_URL e credenciais Cloudinary. DATABASE_URL para leitura das referências aponta para o mesmo banco. Ajuste a referência do código no workflow ao commit/branch revisado.

O script gera dump PostgreSQL custom somente do esquema public do Julib, sem owner/ACL (não inclui esquemas internos auth/storage/extensões do Supabase) e pacote das capas gerenciadas, manifesto e arquivos, cifrado por AES-256-GCM com chave aleatória protegida pela chave pública RSA. Não copia capas externas indisponíveis; guarda suas URLs no banco. Não faz upload parcial nem envia cópia sem cifrar. O limite inicial de pacote é 50 MB; sete pacotes usam até aproximadamente 350 MB, fora outros consumos. Confirme cotas reais no GitHub/Supabase/Cloudinary; a política de inatividade não é SLA. O cliente pg_dump deve ser da mesma versão principal ou mais recente que o servidor.

Retenção de sete dias configurada no artifact privado. O job falha ao exceder o orçamento; não marque “backup completo” se falhar. Deduplicação de mídia e migração para outro destino são próximos passos caso a medição ultrapasse a cota; não estão ativadas silenciosamente. Esse impedimento precisa ser resolvido antes de usar o acervo real em volume incompatível.

## Testar recuperação

Baixe o artifact privado e extraia apenas o arquivo .enc. Descriptografe localmente:

```sh
uv run --project backend python scripts/backup.py decrypt --private /CAMINHO_SEGURO/julib-private.pem --input /CAMINHO_SEGURO/julib-backup.enc --output /CAMINHO_SEGURO/julib-restore.tar.gz
```

Em diretório vazio e privado, liste o tar antes de extrair: contém database.dump, manifest.json e media/. Nunca aceite tar de fonte desconhecida. Restaure em banco **novo e descartável**, nunca na produção durante um teste:

```sh
# Apenas no banco novo e descartável: preparar public vazio e a role das políticas.
# Crie julib_app NOLOGIN no cluster de restauração se a role ainda não existir.
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public'
pg_restore --exit-on-error --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL" database.dump
```

Confira contagens de livros/exemplares/pessoas/empréstimos, relações, estados e imagens conforme manifesto. Para perda da conta Cloudinary, reenviar mídia conforme manifesto e atualizar IDs/URLs nos livros, mantendo correspondência por public_id. Essa migração requer validação manual; não confundir dump restaurado com restauração das imagens concluída. Confirme as duas contas Google e revogue links antigos se houver incidente.

Registre tamanho, hora da última cópia e resultado do teste. Ative notificações de falha do Actions na conta de Marco. Agenda pode atrasar; execução manual e conferência periódica continuam disponíveis. Perda máxima depende da última cópia bem-sucedida, não apenas da agenda diária.

## Rotina

- Conferir consumo e suspensão/inatividade dos planos gratuitos.
- Conferir backup diário e executar teste de recuperação após alterações do mecanismo.
- Conferir `cleanup_imports`, já executado diariamente pelo workflow privado antes do backup, removendo sessões após sete dias sem apagar livros.
- Não registrar contatos, tokens compartilhados ou conteúdo CSV em logs.
- Validar câmera e instalação do PWA nos Chrome do Poco F5 e Samsung A34. Automação em Chromium não substitui teste da câmera física.


## Completar capas de uma importação

Configure GOOGLE_BOOKS_API_KEY apenas no backend, com chave restrita à Books API (sem habilitar faturamento). Execute `uv run --project backend python backend/manage.py enrich_covers --library ID`, com ambiente do banco correto. O comando é retomável: só processa capas ausentes, verifica imagem e limita frequência. Não muda a identidade Goodreads nem outras bibliotecas. Sem correspondência segura, o livro continua sem capa para revisão. URLs externas permanecem nas fontes, com atribuição na interface.

## Reprocessar campos ausentes dos livros

Use `uv run --project backend python backend/manage.py enrich_books --library ID` para consultar livros com campos ausentes. O padrão é somente prévia e informa os campos que poderiam ser preenchidos. Para gravar, acrescente `--apply`; faça antes e valide uma cópia de segurança criptografada recente. O comando consulta somente ISBNs válidos, limita-se à biblioteca informada e só grava cada campo se continuar vazio depois da consulta. Mantém capas existentes (incluindo Cloudinary), demais dados, origem original do cadastro, exemplares e empréstimos. Livros sem ISBN válido ou sem correspondência exata são ignorados. A execução pode ser repetida; `--limit` limita o lote e `--delay` controla o intervalo entre consultas.

## Monitoramento UptimeRobot e prontidão do banco

Monitor HTTP(S): `https://julib.vercel.app/api/v1/health/ready`, intervalo de cinco minutos. GET e HEAD executam a mesma consulta real e somente leitura no PostgreSQL, retornando 200 quando o banco pode ser consultado e 503 genérico quando indisponível. Nenhuma credencial ou informação da biblioteca é devolvida; não precisa configurar autenticação no monitor. Cache-Control é no-store, private.

A conexão da sondagem é independente: connect_timeout=3 segundos, statement_timeout=2 segundos e lock_timeout=1 segundo, locais à transação. A transação é revertida e a conexão fechada; não altera timeouts das requisições comuns. O endpoint antigo /api/v1/health verifica somente o Django. O deploy agora confere /api/v1/health/ready.

O monitor gera atividade real e detecta falhas; não garante que o plano gratuito do Supabase nunca pause nem retoma automaticamente um projeto já pausado. A política considera atividade no banco numa janela de sete dias: https://supabase.com/docs/guides/platform/free-project-pausing. O backup diário também gera consultas reais.

## Migração de desejados e exclusão — 06/11/2026

A migração `0007` acrescenta `Book.is_desired` com default no banco `false`; todos os registros anteriores permanecem no acervo. Recibos de cadastro e linhas concluídas de importação passam a permitir referências nulas quando um cadastro elegível é removido. Chaves e resultados permanecem, impedindo recriação em tentativas antigas. Não limpar esses recibos como parte da exclusão de um livro.

Na publicação que aplicou `0007`, foi usada uma cópia privada prévia. Essa foi uma precaução daquela migração e não cria uma exigência de backup para cada publicação. Para rollback de aplicação, mantenha a migração aplicada; não descarte desejados ou recibos para forçar um esquema antigo. A reversão de `0007` faz preflight e bloqueia se houver desejados ou recibos sem livro/exemplar; uma reversão completa nessas condições exige plano de restauração revisado. Não há exclusão automática de mídia Cloudinary nem empréstimos históricos.

## Operação manual temporária — Actions bloqueado (06/11/2026)

O usuário autorizou pausar o GitHub Actions enquanto o suporte analisa o bloqueio de faturamento da conta. CI e Deploy foram desativados no repositório Julib, e Private daily backup no repositório privado. Os arquivos dos workflows foram preservados. A publicação manual mantém as validações e as migrações revisadas; backup não é uma etapa obrigatória de cada publicação.

Procedimento de publicação:

1. Executar `make check-local` e `make e2e-local` em bancos Docker descartáveis, com servidores locais normais parados durante as jornadas. Exigir sucesso e revisão do código; registrar o commit candidato.
2. Integrar o PR com squash e mensagem explícita. A CI remota pendente só pode ser dispensada conforme autorização já registrada; não registrar execução local como CI remota aprovada. Não reativar workflows automaticamente.
3. Para migrations `0010` e `0011`, antes de produção, executar [multilibrary-preflight.sql](sql/multilibrary-preflight.sql) com role somente leitura. Os nove contadores devem ser zero. Conferir também usuários `is_staff`/`is_superuser`, memberships existentes e `ADMIN_EMAIL`; a migração preserva admins legados, mas não concede capacidade de criação.
4. O backup continua sendo uma rotina operacional independente e não um gate de cada publicação. **Esta mudança de esquema exige, porém, verificar antes da migração que há backup cifrado recuperável:** conferir manifesto/hash, restaurar banco e mídias em ambiente descartável e registrar o resultado. Não usar nem modificar dados reais durante o ensaio.
5. Ensaiar `0010` e `0011` no banco restaurado e descartável, incluindo tempo, locks, validade de constraints e triggers. Repetir o preflight após o restore e confirmar que a migração aplica sem inconsistências. Se os contadores não forem zero ou a validação falhar, interromper e corrigir os dados por processo revisado antes da publicação.
6. Usar `secure_database --role julib_app`, `migrate --noinput` e `secure_database --role julib_app` com `MIGRATION_DATABASE_URL`. Depois da migração, executar `bootstrap_library` com essa conexão para conceder `can_create_libraries` somente à conta configurada por `ADMIN_EMAIL`; confirmar o resultado por leitura. Publicar backend primeiro, confirmar readiness e então publicar o frontend construído do mesmo SHA com o CLI Vercel 65.11.0 e projetos vinculados. Gerar rewrites para `https://julib-api.vercel.app`; segredos ficam no `.env` privado.
7. Validar login, papel/capacidades, acesso com duas bibliotecas em abas distintas, APIs com IDs/cabeçalhos manipulados, importações, empréstimos, upload de capas, compartilhamento público isolado, prontidão, erros e integridade das constraints. Fazer verificações somente de leitura dos dados existentes. Só então executar `python scripts/release.py finalize --sha <SHA-IMPLANTADO>` e registrar as evidências.

**Recuperação após habilitar múltiplas bibliotecas:** não retornar ao backend anterior à Fase 1; ele pode ignorar `X-Library-ID` e operar na primeira membership. Após falha de aplicação, manter as migrations aditivas e corrigir para frente ou redeployar uma versão já compatível com múltiplas bibliotecas. Se houver corrupção que exija recuperação de dados, restaurar o backup validado junto das mídias para um estado consistente e implantar uma versão compatível; a decisão deve considerar e registrar a perda das gravações posteriores ao ponto do backup. Não reverter migrations automaticamente nem mover tags.

Enquanto o Actions estiver pausado, **não há backup diário automático pelo GitHub**. A publicação manual não exige uma nova cópia; o backup operacional continua independente e pode ser executado manualmente quando necessário. Releases manuais não expiram automaticamente como artifacts: na rotina manual, remover somente releases `manual-*` com mais de sete dias, depois de confirmar que não apagará a única cópia necessária à recuperação; não apagar a última cópia válida. Não considerar uma agenda diária restabelecida até reativá-la e validar sua execução.

Após resolução do chamado: reativar CI com `gh workflow enable ci.yml --repo marrcandre/julib`; reativar backup com `gh workflow enable backup.yml --repo marrcandre/julib-backups` e validar uma execução privada; reativar Deploy com `gh workflow enable deploy.yml --repo marrcandre/julib`. Conferir DEPLOY_ENABLED e executar CI do commit atual antes de voltar às publicações automáticas. Não alterar planos nem limites pagos para esse procedimento.

## Diagnósticos no pool de transações

Não executar `SET default_transaction_read_only = on` nem outros `SET SESSION` em diagnósticos pela conexão de runtime. A sessão física é reutilizada pelo pool e uma configuração persistente pode atingir requisições de outros clientes mesmo após fechar a conexão lógica.

Para uma inspeção somente leitura, abrir transação explícita, executar `SET TRANSACTION READ ONLY` antes das consultas e encerrar a transação em todos os caminhos. Com Django, usar `transaction.atomic()` envolvendo todas as consultas. Conferir depois, fora desse bloco, que `SHOW default_transaction_read_only` continua `off`. Timeouts temporários devem usar `SET LOCAL` dentro da transação. Referências: [PostgreSQL SET](https://www.postgresql.org/docs/17/sql-set.html) e [conexões Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

Se houver contaminação de sessão, conferir os defaults do papel/banco e a ausência de recuperação do servidor antes de agir. Renovar somente conexões ociosas do papel de runtime afetado, sem reiniciar o banco ou interromper transações ativas. Validar o caminho de escrita em uma transação revertida, comparando o registro antes/depois. Uma sondagem `SELECT 1` não comprova capacidade de gravação.

## Migração de procedência — 08/11/2026

`0008_book_provenance` adiciona JSONB com default `{}` tanto no ORM quanto no banco. Versões antigas continuam inserindo livros sem conhecer a coluna; registros existentes não são reclassificados. Não remover a coluna num rollback de aplicação, pois novos cadastros podem ter procedência por campo e alternativas de outras fontes. Reverter apresentação/serviços deve preservar a leitura desses créditos enquanto existirem dados derivados de Google Books.

Na migração `0008`, um backup remoto cifrado foi baixado e restaurado como precaução específica da mudança. Isso registra a prática daquela publicação; backup não é requisito geral de deploy. Para alterações futuras, avaliar o risco de perda/transformação de dados e definir a recuperação correspondente. Usar DSN administrativa session pooler, lock_timeout e statement_timeout locais à transação. Conferir hash dos campos antigos sob o lock curto de alteração da tabela antes/depois da expansão. Conferir default do banco, RLS e ausência de grants públicos após aplicar. Publicar backend antes do frontend; nunca executar migração com a role de runtime ou tornar a sessão do pool somente leitura.

## Versionamento do produto

`frontend/package.json` é a fonte canônica de build; `frontend/package-lock.json`, `backend/pyproject.toml` e `backend/uv.lock` devem permanecer sincronizados. O bundle Vite incorpora a versão sem chamada à API. A versão OpenAPI continua independente. A versão implantada em `679e706` é `0.1.0`, usada como baseline histórico; `v0.2.0` já foi publicada. Para a Fase 1 de múltiplas bibliotecas, o candidato é `0.3.0` (MINOR). MAJOR indica incompatibilidade, MINOR funcionalidade compatível e PATCH correção ou manutenção, incluindo publicação de infraestrutura.

Prepare o número explicitamente antes de integrar o PR: `python scripts/release.py prepare minor` (ou `patch`/`major`). O helper sincroniza os metadados e uma repetição durante a publicação mantém o mesmo candidato. `python scripts/release.py validate` exige candidato ainda não publicado. O workflow Deploy valida antes da migração e finaliza a tag anotada e a GitHub Release, com notas automáticas, somente depois dos dois deploys e da sondagem pública. Backup é uma rotina independente, não um gate de release. Enquanto Actions estiver pausado, use esses passos no processo manual; editar o workflow não reativa Actions.

### Alertas de dependências adiados

A auditoria desta worktree reportou 10 nós de pacotes afetados (8 moderados e 2 críticos). `npm audit --omit=dev` não reportou vulnerabilidades: os nós afetados são dependências de desenvolvimento/teste, não do bundle/runtime de produção. Os dois críticos estão no `tinypool` transitivo de `vitest@3.2.7` (`tinypool@1.1.1`): [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) trata de prototype pollution/opções de worker com impacto de execução de código; [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) trata de opções de `run()` com impacto de execução de código. A correção informada para `tinypool` é 2.1.2 ou posterior, exigindo atualização coordenada do Vitest.

Os moderados incluem dois problemas em `@vitest/mocker@3.2.7` — leitura arbitrária de arquivos via redirect mock ([GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)) e injeção de código por registro de mock via WebSocket do Vite ([GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8)) — e avisos de `glob` ([GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4)) e `minimatch` ([GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249)). O relatório também lista caminhos transitivos que carregam esses avisos, como `@vue/language-core`, `vue-tsc`, `@vue/test-utils`, `js-beautify` e `editorconfig`; por isso os dez nós afetados não significam dez vulnerabilidades independentes.

Criar tarefa posterior para atualizar Vitest/mocker e resolver o grafo transitivo com versões compatíveis, revisar o lockfile e repetir auditoria completa, testes e build. Até lá, não expor servidor Vite/HMR a clientes não confiáveis nem reativar execução pública de testes/CI sem tratar esses alertas. Não aplicar `npm audit fix` indiscriminadamente. Nesta revisão não foi identificada vulnerabilidade efetivamente explorável no runtime de produção.

Em falha de deploy, não finalize: repita o mesmo candidato e SHA sem novo incremento. Se a tag foi criada mas a GitHub Release falhou, repita `finalize`; a operação é idempotente. Um rollback de código já publicado exige novo PATCH. Nunca mova tags nem reverta migrações automaticamente.
