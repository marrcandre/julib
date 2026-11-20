# Operação do Julib

Operação ativa: aplicação publicada e integrações configuradas. O backup de produção de 19/11/2026 foi descriptografado, verificado e restaurado em PostgreSQL 17.11 descartável, conforme o [registro operacional](#validação-operacional--19112026). O workflow de backup permanece desativado manualmente e `DEPLOY_ENABLED=false`. A automação futura está proposta no [backlog](backlog.md#automatizar-backups-de-produção-e-validar-recuperação-periódica). Consulte também o histórico de implementação e a [auditoria de requisitos](reviews/2026-11-05-requisitos-e-proximas-entregas.md), cujos registros refletem as datas indicadas.

## Configuração privada

Copie `.env.example` para `.env`; não publique esse arquivo. `ALLOWED_EMAILS` contém os dois e-mails verificados pelo Google; `ADMIN_EMAIL` é um deles. Apenas essa conta recebe staff/superuser para o Django Admin. Sessões continuam sujeitas à allowlist em cada chamada; remover um e-mail bloqueia a API imediatamente.

Use SECRET_KEY aleatória longa, DEBUG=false em produção, ALLOWED_HOSTS explícitos e CSRF_TRUSTED_ORIGINS com a origem pública HTTPS. O contato/PIX público do autor não determina o e-mail de login.

## Convites e gestão de membros

### Convites para criação de bibliotecas

O proprietário técnico pode emitir, consultar e revogar convites pela área Julib **Convites para criar bibliotecas** ou pelo Django Admin. Convites têm uso único e validade de sete dias; podem ser livres ou vinculados a um e-mail. O Julib não envia e-mail: copie o link apresentado na emissão e encaminhe-o ao destinatário. O token bruto só aparece nessa resposta/mensagem de emissão; o banco guarda SHA-256 e as listagens mostram somente metadados, estado e a biblioteca resultante.

O link usa `/convites/criar#<token>`. A página remove o fragmento da barra de endereço antes da primeira chamada à API. A sessão guarda somente o hash do convite durante o OAuth. E-mail vinculado exige que a conta Google autenticada apresente aquele mesmo endereço verificado; link livre aceita qualquer conta Google com e-mail verificado.

A migration aditiva `0015_librarycreationinvite` cria uma tabela separada dos convites de participação. A relação única entre convite consumido e biblioteca, além das constraints de estado e validade, impede associar mais de uma biblioteca ao convite. Ao resgatar, o backend bloqueia a linha do convite com `select_for_update`, revalida validade, revogação, uso e identidade dentro da transação, e cria biblioteca, membership `admin` e consumo no mesmo commit. Revogação bloqueia a mesma linha e revalida o estado: se revogar confirmar primeiro, o consumo aguardando é recusado; se o consumo confirmar primeiro, revogar retorna conflito. Dois resgates simultâneos resultam em no máximo uma biblioteca. A garantia não depende de remover cookies ou limpar sessões. Os testes de corrida devem ser executados em PostgreSQL real; SQLite não comprova essa serialização.

Uma conta fora da allowlist pode usar uma sessão com convite de criação somente para concluir o resgate. O convite não altera `can_create_libraries`, `staff`, allowlist nem memberships existentes. Depois do consumo, a autorização de acesso à biblioteca deriva do convite associado à biblioteca e da membership administrativa; a criação comum em `/libraries` continua exigindo a capacidade global existente. O token não é registrado em logs.

Para validação local, use a base PostgreSQL descartável configurada no fluxo de desenvolvimento (`make db`; pytest cria `test_julib`, e `make e2e-local` usa `julib_e2e`). Confira a migration e o schema e execute `secure_database --role julib_app` com a credencial administrativa no procedimento de publicação, para a tabela nova manter RLS e grants restritos ao backend. Não ensaie nem execute a migration em produção como parte de desenvolvimento. Esta alteração não escolhe versão; classifique o conjunto efetivo da publicação e use `scripts/release.py` conforme a seção de versionamento.

### Convites para participar de bibliotecas existentes

Administradores de cada biblioteca podem gerar links de convite de uso único, com validade de sete dias, e revogá-los. O link retorna o token apenas na criação; listagens nunca contêm tokens. O navegador mantém o token somente em memória durante a preparação: ele é lido do fragmento (`#...`) e removido da barra de endereço antes da chamada ao backend. O backend guarda somente SHA-256 do token na sessão Django e valida a sessão OAuth/CSRF normalmente. Links devem ser tratados como credenciais temporárias e compartilhados apenas com o destinatário.

Para aceitar, é necessário entrar com Google e endereço verificado. Um convite válido permite a conta convidada fora da `ALLOWED_EMAILS` somente para concluir o ingresso naquela biblioteca; não concede criação de bibliotecas nem outras memberships. O novo papel é `member`. Usuários já membros recebem confirmação sem membership duplicada e o link permanece disponível para outro destinatário. Convites aceitos não podem ser revogados; revogar ou expirar um link pendente invalida a sessão que o preparou.

O início do cadastro OAuth por convite fica marcado na sessão de backend pelo hash do convite. No callback, o backend valida novamente convite, biblioteca, expiração, revogação e e-mail Google verificado antes de salvar a conta. Se o contexto deixar de ser válido, o cadastro é interrompido; ele não segue pelo fluxo comum nem recebe membership da primeira biblioteca. A conta nova só entra na biblioteca depois de aceitar o convite autenticado.

A alteração de papéis e a remoção de memberships passam pelos mesmos serviços transacionais usados pela API e pelo Django Admin. O Admin também protege exclusões individuais e em lote de memberships e usuários, inclusive cascatas que removam memberships. As mutações bloqueiam as linhas da biblioteca em ordem estável e recontam administradores dentro da transação; exclusões de usuários bloqueiam as bibliotecas antes de avaliar todas as memberships afetadas. Não remova memberships diretamente por scripts ou operações de queryset fora desses serviços. Valide concorrência em PostgreSQL: SQLite não oferece os mesmos bloqueios.

A migração `0012_library_invites_and_membership_provenance` adiciona a tabela de convites e a proveniência da membership sem preencher datas históricas artificiais. A `0013_invite_membership_library_constraint` acrescenta uma FK composta que impede associar membership e convite de bibliotecas diferentes; ela é `NOT VALID` para evitar varredura bloqueante dos registros históricos e já valida escritas novas. Antes de aplicá-las em produção, executar `docs/sql/multilibrary-preflight.sql` e revisar os resultados, confirmar backup recuperável, restaurar esse backup em banco PostgreSQL descartável e ensaiar as migrations pendentes. Nunca fazer esse ensaio na produção. `select_for_update` serializa mudanças de papel/remoção/saída de administradores por biblioteca; valide essa garantia em PostgreSQL, pois SQLite não implementa os mesmos locks.

Publicação coordenada: aplicar migrations com a credencial administrativa dedicada, publicar o backend e confirmar health/readiness e login Google; depois publicar o frontend construído do mesmo SHA. Validar criação, compartilhamento, aceite em conta Google fora da allowlist, papel `member`, ausência de acesso a outras bibliotecas, membro já existente, revogação, expiração, gestão de papéis e proteção do último administrador. Após mudança de schema, não retornar a backend que ignore isolamento por biblioteca. Em falha, corrigir para frente ou implantar código compatível; para corrupção, restaurar backup e mídias em estado consistente e usar código compatível, registrando a perda posterior ao backup.

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

URI de retorno local usando o proxy: `http://127.0.0.1:5173/accounts/google/login/callback/`. Produção: `https://julib.vercel.app/accounts/google/login/callback/`. A origem pública deve estar nos hosts/CSRF Django. Defina APP_ORIGIN=https://julib.vercel.app no runtime de produção para o callback usar a interface atrás do proxy; mantenha vazio no desenvolvimento local. Não coloque o domínio do backend como callback se a sessão for utilizada pela origem frontend.

O link de entrada abre a confirmação OAuth do allauth. São aceitos e-mails Google verificados em allowlist, com convite válido para o ingresso inicial ou com membership ativa derivada de convite já aceito. O login posterior do membro não depende de reutilizar o convite; remover sua membership revoga esse acesso. Novos usuários comuns da allowlist são associados à biblioteca inicial no provisionamento OAuth, e contas já existentes mantêm suas memberships. Um cadastro que começou por convite fica vinculado a ele até a validação no callback e só recebe membership ao aceitar o convite. Use `bootstrap_library` para provisionar memberships de usuários existentes da allowlist. A migração `0010` conserva as memberships existentes, atribui o papel administrativo às contas técnicas existentes e armazena a permissão explícita de criar bibliotecas. Essa capacidade fica no usuário; não é derivada do papel na biblioteca durante as chamadas da API. Valide o login e a permissão de criação com a conta administrativa e uma conta sem essa capacidade.

**Verificação manual em produção:** confira no ambiente Django `APP_ORIGIN=https://julib.vercel.app`, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` para a origem HTTPS pública. No cliente OAuth Web do Google, confirme a URI autorizada `https://julib.vercel.app/accounts/google/login/callback/`; segredos continuam apenas no backend. Em janela privada, inicie login pela interface, confira que o navegador volta pela URL de callback acima e conclui em `/livros` com sessão válida. Repita com uma conta permitida e uma conta fora da allowlist sem convite; a segunda deve ser recusada sem criar usuário ou membership. Não copie `code`, `state`, cookies ou tokens para logs. Não use login local para validar a callback do Google.

## Migração para múltiplas bibliotecas

As migrações `0010` e `0011` são aditivas. `0010` adiciona papel à membership e a permissão global de criação sem copiar nem alterar livros, empréstimos, IDs de biblioteca ou referências Cloudinary. A migração mantém admins legados (memberships de usuários `is_staff`) e deixa `can_create_libraries` falso; `bootstrap_library` concede essa capacidade à conta correspondente ao `ADMIN_EMAIL`. `0011` acrescenta chaves e FKs compostas para locais, exemplares, empréstimos e recibos de cadastro, além de triggers de integridade para tags e linhas de importação.

Esta `0010` ainda não foi publicada e foi corrigida diretamente. Um banco de desenvolvimento que já registrou a versão anterior da migração não executará o novo `RunPython` automaticamente; confira `can_create_libraries` nesse banco e, se for descartável, recrie-o para exercitar o histórico corrigido. Não use um banco de produção para esse procedimento.

Antes de aplicar `0011`, execute o preflight somente de leitura descrito abaixo. Ele confere também tags de livros e exemplares de linhas de importação; essas tabelas não armazenam uma coluna de biblioteca compartilhada e são protegidas por triggers. As constraints compostas são validadas na migração; os triggers protegem novas relações e mudanças posteriores, enquanto o preflight detecta relações antigas inconsistentes. Investigue e corrija qualquer divergência antes de repetir.

Publique backend e frontend juntos antes de criar uma segunda biblioteca. A API mantém compatibilidade para contas com uma única membership sem cabeçalho de contexto; contas com várias memberships precisam enviar `X-Library-ID`, que o backend valida a cada operação. A URL da interface determina esse cabeçalho por aba. Depois que houver mais de uma biblioteca, não faça rollback para uma versão anterior à Fase 1: ela ignora o cabeçalho e pode operar na primeira membership. Use correção para frente ou uma versão de rollback que suporte múltiplas bibliotecas.

### Migration `0014` — search_path dos triggers

A migration forward-only `0014_secure_integrity_trigger_search_path` substitui os corpos das quatro funções `julib_check_*` sem trocar nomes, assinaturas, triggers ou regras de integridade. Cada função fixa `search_path = pg_catalog, public, pg_temp`; `pg_temp` fica explicitamente por último, e cada tabela da aplicação aparece qualificada como `public.<tabela>`. Isso impede que uma tabela temporária com nome coincidente altere a leitura feita pelo trigger. A migration não altera tabelas nem linhas existentes, por isso não requer backfill e preserva os relacionamentos atuais; ensaie em PostgreSQL 17 descartável antes de aplicar. Não reverta: se uma publicação falhar, corrija para frente. Após o ensaio, confira novamente o Supabase Advisor e que as quatro `proconfig` exibem o search path esperado.

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

## Backup cifrado no repositório privado

O destino aprovado continua sendo o repositório privado `julib-backups`. Em 19/11/2026, o template `ops/backup-workflow.yml.example` foi instalado como `.github/workflows/backup.yml`; o workflow permanece `disabled_manually` e aceita somente `workflow_dispatch`, sem agendamento nem execução de `cleanup_imports`. Ele usa runner hospedado `ubuntu-latest`, permissão `contents: read`, verifica que o repositório é privado e envia somente o pacote cifrado e o sidecar SHA-256 como artifact por 30 dias. A retenção padrão configurada no repositório é 90 dias, com máximo permitido de 400; a retenção individual do artifact continua em 30 dias. A ativação e qualquer execução real exigem autorização explícita. Artifacts expiram; uma política de cópia permanente, versionada e independente precisa ser aprovada à parte.

### Preparar uma execução manual

- Confirme que o workflow ainda está desabilitado até a autorização e que o repositório privado está acessível aos operadores responsáveis.
- Confirme a disponibilidade da chave pública de cifragem em secret, da chave privada de recuperação e de uma segunda cópia segura da chave privada. Nunca copie a chave privada para Actions.
- Configure `BACKUP_DATABASE_URL` com usuário dedicado sem DML/DDL, autorizado a conectar, usar o schema `public` e ler as tabelas e sequências necessárias. Confirme também que a role pode ler **todas** as linhas protegidas por RLS: o código não altera policies, e o dump padrão falha se não puder garantir que todas as linhas foram exportadas. A policy documentada para `julib_app` é específica dessa role; não presuma que uma nova role herdará essa visibilidade. O padrão do `pg_dump` desativa row security para não omitir linhas e falha sem privilégio suficiente; `--enable-row-security` pode exportar somente as linhas visíveis e é inadequado como desvio sem uma política comprovadamente completa ([documentação PostgreSQL](https://www.postgresql.org/docs/17/app-pgdump.html)). Use a mesma conexão de leitura em `DATABASE_URL` para a consulta de referências das capas. O template injeta ambas como secrets do job; o filho `pg_dump` recebe um DSN sem senha e um arquivo `PGPASSFILE` temporário, modo `0600`, removido mesmo quando o comando falha.
- Se nenhuma role sem DML/DDL puder ler todas as linhas, pare e peça aprovação para provisionar uma permissão/policy de leitura específica; não contorne a falha com a credencial administrativa nem conceda `BYPASSRLS` à role de runtime.
- Configure apenas as credenciais de leitura necessárias da API Cloudinary como secrets do repositório. Não use `CLOUDINARY_URL` junto das variáveis individuais.
- Confirme espaço temporário suficiente, versão do cliente `pg_dump` compatível com o servidor, limite padrão de 50 MiB e consumo/cota do artifact. Não reduza cobertura nem aumente o limite sem uma medição e decisão registradas.
- Verifique os nomes e a presença dos secrets sem imprimir seus valores. Não use `env`, `set -x`, `printenv`, comandos que mostrem o DSN ou logs completos do provedor.

A geração manual local usa a mesma implementação revisada, com ambiente privado carregado por um gerenciador de secrets aprovado, sem colocar valores em argumentos ou arquivos versionados:

```sh
uv run --project backend python scripts/backup.py create --public /CAMINHO_SEGURO/julib-public.pem --output /DIRETORIO_PRIVADO/julib-backup-DATA.enc --media
```

O comando precisa de `BACKUP_DATABASE_URL`, `DATABASE_URL` e credenciais Cloudinary no ambiente privado. Não execute o comando até aprovar expressamente o acesso ao banco de produção. O dump PostgreSQL custom inclui apenas o schema `public`, sem owner/ACL. Esquemas internos do Supabase, roles globais, configuração do projeto e identidades do Supabase Auth ficam fora do pacote; prepare roles e permissões necessárias separadamente no destino descartável. O usuário do restore será o proprietário dos objetos restaurados e grants originais não são reconstituídos automaticamente.

O pacote usa envelope `JULIB01`: AES-256-GCM com chave aleatória protegida por RSA-OAEP. A geração escreve dump, pacote e cifra em arquivos de uma pasta temporária privada (modo `0700`), publica o arquivo final por substituição atômica e remove a pasta temporária ao terminar. O limite cifrado padrão permanece 50 MiB; cada mídia tem teto de 8 MiB e o verificador limita o conteúdo descompactado a 512 MiB. Uma execução que ultrapasse limites, fique sem espaço, falhe no PostgreSQL/Cloudinary ou detecte alterações nas referências do banco ou versão dos assets é interrompida sem publicar pacote parcial. PostgreSQL e Cloudinary não oferecem snapshot transacional conjunto: as comparações reduzem e detectam divergências observadas, mas não provam que nenhuma alteração breve ocorreu entre as leituras.

Manifesto versão 2 contém data de geração, ID público Cloudinary, caminho relativo, tamanho e SHA-256 de cada arquivo. URLs assinadas, credenciais e dados de livros não são adicionados ao manifesto. Capas externas não são copiadas; o banco mantém suas URLs, que dependem da disponibilidade da fonte.

### Verificar integridade

Calcule o hash cifrado antes de transferir e guarde-o no registro operacional. Após baixar o artifact, confira o sidecar e execute o verificador com a chave privada local:

```sh
(cd /DIRETORIO_PRIVADO_DO_ARTIFACT && sha256sum -c ./*.enc.sha256)
uv run --project backend python scripts/backup.py verify --private /CAMINHO_SEGURO/julib-private.pem --input /DIRETORIO_PRIVADO_DO_ARTIFACT/julib-backup.enc --sha256 SHA256_REGISTRADO
```

O verificador compara o SHA-256 do arquivo cifrado, autentica AES-GCM, valida o tar sem extrair caminhos, exige dump e manifesto, rejeita caminhos/entradas duplicadas ou extras e recalcula tamanho/hash de todas as mídias. Manifestos versão 1, gerados antes deste ajuste e sem hashes por mídia, continuam verificáveis por presença e estrutura; novos backups usam versão 2. A verificação não prova que serviços externos ou permissões do Supabase estejam prontos para recuperação.

### Restaurar em ambiente descartável

A restauração de teste deve usar PostgreSQL descartável, nunca produção. Primeiro valide o `.enc` com `verify`, depois descriptografe para uma pasta privada vazia:

```sh
uv run --project backend python scripts/backup.py decrypt --private /CAMINHO_SEGURO/julib-private.pem --input /DIRETORIO_PRIVADO_DO_ARTIFACT/julib-backup.enc --output /DIRETORIO_PRIVADO/julib-restore.tar.gz
mkdir -m 700 /DIRETORIO_PRIVADO/restore
cd /DIRETORIO_PRIVADO/restore
tar -xOf ../julib-restore.tar.gz database.dump > database.dump
```

Prepare no cluster descartável o role sem login referenciado nas políticas (por exemplo `julib_app`) antes da restauração e confira como serão atribuídos proprietários e grants, pois o dump exclui owner e ACL. Configure libpq por variáveis `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE` e `PGPASSFILE` modo `0600`; não passe senha em argumento. Somente no banco descartável, prepare schema vazio e execute:

```sh
psql -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public'
pg_restore --exit-on-error --no-owner --no-acl --schema=public database.dump
```

Compare tabelas, relações, estados e contagens de livros, exemplares, pessoas, empréstimos e recibos com o manifesto operacional aprovado. Não registre linhas ou conteúdo de dados nos logs. O pacote de mídia deve ser conferido pelo `verify`; não considere apenas a restauração do banco como recuperação completa.

### Enviar e reter a cópia cifrada

O fluxo opcional `ops/upload-existing-backup-workflow.yml.example` exige runner próprio restrito a `julib-backups`, lê a pasta de entrada sem escrita para a conta do runner e valida nome, tamanho, envelope e SHA-256 antes de enviar um arquivo cifrado como artifact por 30 dias. Em 19/11/2026, esse workflow não estava instalado e não havia runner próprio registrado. O fluxo principal instalado gera e envia o artifact cifrado na mesma execução manual; valide previamente o procedimento e obtenha autorização antes de ativá-lo ou executá-lo. Registre ID da execução, SHA-256, data de criação e expiração. Não trate artifacts como cópia permanente; releases manuais antigas não expiram automaticamente e não devem ser removidas sem revisão e autorização.

### Recuperar mídias Cloudinary

O manifesto liga cada `public_id` ao arquivo validado no pacote. Após descriptografar em pasta privada, escreva o manifesto sem imprimi-lo no terminal e extraia apenas os caminhos validados:

```sh
tar -xOf /DIRETORIO_PRIVADO/julib-restore.tar.gz manifest.json > /DIRETORIO_PRIVADO/manifest.json
chmod 600 /DIRETORIO_PRIVADO/manifest.json
tar -xOf /DIRETORIO_PRIVADO/julib-restore.tar.gz media/0.jpg > /DIRETORIO_PRIVADO/cover-0.jpg
chmod 600 /DIRETORIO_PRIVADO/cover-0.jpg
```

Para perda do conteúdo ou da conta, restaure cada imagem em uma conta de recuperação preservando a correspondência entre `public_id` e livro; valide URL e imagem antes de ajustar referências no banco. O upload em conta nova ou a atualização de referências em produção exige plano e autorização próprios, pois IDs/URLs podem mudar e Cloudinary e PostgreSQL não compartilham transação. Nunca faça esse ensaio usando a conta de produção.

### Registro operacional e autorização

Registre data/hora, commit da implementação usado, run ID, tamanho, SHA-256 cifrado, formato do manifesto, contagens resumidas, número de mídias, resultado de `verify`, resultado do restore descartável, destino e expiração. Não registre credenciais, DSNs, URLs assinadas, linhas de livros ou manifesto completo.

Antes de qualquer execução real, transferência, ativação de workflow ou recuperação em serviço real, peça autorização explícita. A execução de 19/11/2026 abaixo foi autorizada e validada; o workflow voltou a ficar desativado. `DEPLOY_ENABLED` permanece `false`. A exigência de autorização própria para Fases 3 e 4 era o estado registrado em 19/11; a publicação autorizada e concluída em 20/11 está registrada em [Publicação Fases 3 e 4 — v0.7.0](#publicação-das-fases-3-e-4--v070).

### Validação operacional — 19/11/2026

A primeira cópia de produção validada após a correção Cloudinary da versão `v0.6.1` foi gerada na segunda tentativa, pela [execução 44605863622](https://github.com/marrcandre/julib-backups/actions/runs/44605863622). A tentativa anterior, `44578487411`, falhou na verificação final das mídias e não constitui backup validado.

| Evidência | Resultado |
| --- | --- |
| Versão e commit do código de backup | `v0.6.1`, `b4a15b5794277f3ccbf3c0940c9cdfdcffd9b967` (`b4a15b5`) |
| Repositório privado | `marrcandre/julib-backups` |
| Execução | `44605863622`, concluída com sucesso em 19/11/2026 |
| Data de geração no manifesto | `2026-11-19T20:12:23.052976+00:00` |
| Artifact | `julib-backup-44605863622` |
| Arquivo criptografado | `julib-backup-44605863622.enc`, 13.848.331 bytes, abaixo do limite de 50 MiB |
| SHA-256 do arquivo criptografado | `3067b1b606f5360b762fa18fc9577b2616942faacf25766de6708e2f76fc7b1f` |
| Formato | Envelope criptografado `JULIB01`, manifesto versão 2 |
| Retenção e expiração do artifact | 30 dias; 19/12/2026 |
| Descriptografia e verificação interna | Aprovadas; autenticação AES-GCM, SHA-256 do sidecar e integridade do pacote conferidos |
| Restauração | Aprovada com servidor PostgreSQL 17.11 e `pg_restore` 17.11 em container descartável sem rede |
| Estrutura e registros restaurados | 33 tabelas, 32 sequências e 1.577 registros no total; 33 tabelas com RLS e 33 policies |
| Mídias Cloudinary | 371 arquivos verificados por tamanho e SHA-256 contra o manifesto |
| Estado final do workflow | `disabled_manually`, exclusivamente manual e sem `schedule` |

O artifact cifrado e o relatório operacional seguro foram preservados localmente fora do repositório, em diretório privado. O pacote descriptografado, o dump temporário e o container de teste foram removidos após a validação. O teste de restauração não fez alterações em produção nem chamadas de escrita ao Supabase ou Cloudinary.

As 33 tabelas e 32 sequências restauradas correspondem ao índice de objetos (TOC) do dump. O manifesto não registra contagens de tabelas ou de linhas: os 1.577 registros foram contados somente no banco restaurado e não foram comparados com uma nova leitura da produção. O restore foi executado sem owners/ACLs, com a role `julib_app` preparada no destino para as policies; isso não comprova a reconstrução automática das permissões de produção.

Limitações conhecidas:

- PostgreSQL e Cloudinary não compartilham snapshot transacional. A comparação de referências e metadados antes/depois reduz a janela de inconsistência observada, mas não garante atomicidade entre os serviços.
- O pacote cobre o schema `public` e as mídias referenciadas pelo processo. Schemas administrativos, roles globais, Supabase Auth, configurações de serviços e outros serviços externos não são cobertos integralmente. Capas externas continuam dependendo das URLs de origem.
- A recuperação depende da preservação segura da chave privada correspondente, fora do GitHub, com uma segunda cópia segura recuperável. A chave privada não integra este registro nem o artifact.
- Artifacts têm retenção limitada e expiram; o artifact desta execução expira em 19/12/2026. A cópia externa criptografada em armazenamento independente é proposta futura, sem implementação nesta etapa.

A tarefa [Automatizar backups de produção e validar recuperação periódica](backlog.md#automatizar-backups-de-produção-e-validar-recuperação-periódica) registra os requisitos propostos para a próxima etapa. A rotina diária permanece desativada.

## Completar capas de uma importação

Configure GOOGLE_BOOKS_API_KEY apenas no backend, com chave restrita à Books API (sem habilitar faturamento). Execute `uv run --project backend python backend/manage.py enrich_covers --library ID`, com ambiente do banco correto. O comando é retomável: só processa capas ausentes, verifica imagem e limita frequência. Não muda a identidade Goodreads nem outras bibliotecas. Sem correspondência segura, o livro continua sem capa para revisão. URLs externas permanecem nas fontes, com atribuição na interface.

## Reprocessar campos ausentes dos livros

Use `uv run --project backend python backend/manage.py enrich_books --library ID` para consultar livros com campos ausentes. O padrão é somente prévia; `--apply` grava apenas campos que continuam vazios após uma nova leitura sob lock. O comando limita-se à biblioteca informada, preserva valores e proveniência não editados, não altera tags pessoais e é idempotente para os campos preenchidos. Nunca execute `--apply` em produção como parte desta entrega.

Para salvar um relatório detalhado, informe os dois argumentos abaixo; `--report-format` aceita `csv` ou `json`, e o arquivo é criado com permissão somente para o usuário atual. A prévia continua sem gravações:

```sh
uv run --project backend python backend/manage.py enrich_books --library ID --report-format csv --report-file /CAMINHO_SEGURO/enrich-preview.csv
uv run --project backend python backend/manage.py enrich_books --library ID --report-format json --report-file /CAMINHO_SEGURO/enrich-preview.json
```

Para exercitar gravações e comparar o banco antes/depois, use exclusivamente uma biblioteca e banco locais ou descartáveis; o modo real exige `--apply`:

```sh
uv run --project backend python backend/manage.py enrich_books --library ID --report-format json --report-file /CAMINHO_SEGURO/enrich-apply.json --apply
```

O relatório JSON tem `mode`, `summary` e `details`; o CSV contém uma linha `summary` com o modo e os agregados e uma linha `detail` para cada livro/campo. Cada detalhe identifica `book_id`, ISBN, título, campo, situação, valor e provedor. Situações: `já preenchido`, `seria preenchido`, `preenchido`, `não encontrado` e `erro`. Listas de assuntos no CSV são codificadas como array JSON numa única célula. Para evitar fórmulas em planilhas, células CSV iniciadas por `=`, `+`, `-` ou `@` (inclusive após espaços de controle) recebem apóstrofo inicial; JSON preserva os valores originais. Em `apply`, `preenchido` e os contadores `fields_filled` incluem somente valores persistidos após a releitura sob lock; candidatos que perderam uma disputa aparecem como erro sem valor alegado como gravado. `fields_would_fill` aparece na prévia; `fields_found` conta candidatos válidos. Falhas por provedor são contadas individualmente, inclusive HTTP 429. O comando não faz consultas adicionais para montar relatórios. A saída resumida e a linha `JSON:` no terminal são mantidas por compatibilidade.

O resolvedor consulta cada adaptador de provedor no máximo uma vez por operação e escolhe cada campo independentemente, com fallback quando uma fonte não fornece aquele campo. A ordem global provisória é Open Library → Google Books → BrasilAPI/CBL → BrasilAPI/Mercado Editorial; prioridades continuam declaradas por campo em `FIELD_PRIORITIES` e podem divergir. A ordem é uma hipótese operacional temporária, não uma superioridade comprovada. Não há classificação regional nem dependência operacional da International ISBN Agency; qualquer ISBN válido e normalizado pode ser consultado. A correspondência da edição permanece exata por ISBN. HTTP 429 encerra a tentativa daquele provedor e permite fallback para os seguintes; não há retry, backoff ou tratamento de `Retry-After`. Um adaptador pode fazer mais de uma requisição HTTP: Open Library consulta os formatos `data` e `details` e pode consultar a obra para obter descrição.

Limites dos campos novos: subtítulo até 500 pontos de código Unicode; descrição até 20.000; assuntos até 50 itens distintos, cada um com no máximo 200. Valores de provedor acima do limite são rejeitados integralmente e permitem fallback; nunca são truncados silenciosamente. Descrições são convertidas de HTML simples para texto seguro. A descrição da Open Library registra se veio de uma edição ou da obra. Assuntos bibliográficos não são tags. A ficha mostra a descrição recolhida inicialmente e assuntos numa seção separada.

Na saída normal, o relatório por livro lista fontes consultadas, correspondências/divergências de ISBN, campos encontrados com suas fontes, campos preenchidos ou preservados e falhas. Descrições aparecem resumidas na prévia; a linha `JSON:` final contém métricas agregadas por campo e provedor para análise futura. A exportação detalhada CSV/JSON é opcional e usa a mesma resposta do provedor, sem consultas adicionais. Use `--limit` para limitar o lote e `--delay` para controlar o intervalo entre livros. Faça qualquer ensaio de migration ou concorrência em PostgreSQL descartável; não use o banco de produção em testes.

Uma avaliação exploratória de provedores, com amostra fixa de seis ISBNs, método reproduzível, resultados observados e limitações está registrada em [avaliação de provedores de 20/11/2026](reports/2026-11-20-book-provider-evaluation.md). Ela não altera a prioridade proposta nem substitui uma comparação com quota Google válida.

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

Enquanto o Actions estiver pausado, **não há backup automático pelo GitHub**. O template revisado é manual e não exige reativar agendas. Releases `manual-*` criadas pela rotina antiga não expiram automaticamente e ficam fora da retenção proposta de artifacts por 30 dias. Preserve essas cópias até revisar sua validade; não as exclua automaticamente. Não considerar workflow, retenção ou acesso ao artifact confirmados sem conferência no repositório privado.

Após resolução do chamado, reativar CI e Deploy conforme aprovação operacional própria. Para backup, copiar o template manual para `julib-backups` e obter autorização explícita antes de habilitar Actions ou iniciar uma execução. Conferir DEPLOY_ENABLED e executar CI do commit atual antes de voltar às publicações automáticas. Não alterar planos nem limites pagos para esse procedimento.

## Diagnósticos no pool de transações

Não executar `SET default_transaction_read_only = on` nem outros `SET SESSION` em diagnósticos pela conexão de runtime. A sessão física é reutilizada pelo pool e uma configuração persistente pode atingir requisições de outros clientes mesmo após fechar a conexão lógica.

Para uma inspeção somente leitura, abrir transação explícita, executar `SET TRANSACTION READ ONLY` antes das consultas e encerrar a transação em todos os caminhos. Com Django, usar `transaction.atomic()` envolvendo todas as consultas. Conferir depois, fora desse bloco, que `SHOW default_transaction_read_only` continua `off`. Timeouts temporários devem usar `SET LOCAL` dentro da transação. Referências: [PostgreSQL SET](https://www.postgresql.org/docs/17/sql-set.html) e [conexões Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

Se houver contaminação de sessão, conferir os defaults do papel/banco e a ausência de recuperação do servidor antes de agir. Renovar somente conexões ociosas do papel de runtime afetado, sem reiniciar o banco ou interromper transações ativas. Validar o caminho de escrita em uma transação revertida, comparando o registro antes/depois. Uma sondagem `SELECT 1` não comprova capacidade de gravação.

## Migração de procedência — 08/11/2026

`0008_book_provenance` adiciona JSONB com default `{}` tanto no ORM quanto no banco. Versões antigas continuam inserindo livros sem conhecer a coluna; registros existentes não são reclassificados. Não remover a coluna num rollback de aplicação, pois novos cadastros podem ter procedência por campo e alternativas de outras fontes. Reverter apresentação/serviços deve preservar a leitura desses créditos enquanto existirem dados derivados de Google Books.

Na migração `0008`, um backup remoto cifrado foi baixado e restaurado como precaução específica da mudança. Isso registra a prática daquela publicação; backup não é requisito geral de deploy. Para alterações futuras, avaliar o risco de perda/transformação de dados e definir a recuperação correspondente. Usar DSN administrativa session pooler, lock_timeout e statement_timeout locais à transação. Conferir hash dos campos antigos sob o lock curto de alteração da tabela antes/depois da expansão. Conferir default do banco, RLS e ausência de grants públicos após aplicar. Publicar backend antes do frontend; nunca executar migração com a role de runtime ou tornar a sessão do pool somente leitura.

## Versionamento do produto

O Julib adota Semantic Versioning na forma `MAJOR.MINOR.PATCH`. Incrementar MAJOR para mudanças incompatíveis que exijam ajustes em clientes, integrações ou contratos existentes; MINOR para funcionalidades e melhorias compatíveis; PATCH para correções de bugs e pequenos ajustes sem novas funcionalidades. Classificar pelo conteúdo efetivamente incluído na publicação, não pelo número de commits, tarefas internas ou fases concluídas. Não incrementar por commit ou tarefa; agrupar alterações da mesma etapa quando fizer sentido.

Toda publicação em produção deve ter versão identificável. Atualizar e validar a versão antes de publicar e registrar no changelog as mudanças relevantes de cada versão. O Julib não mantém arquivo de changelog separado: as notas da GitHub Release, geradas por `release.py` a partir das alterações, são o registro de mudanças por versão. Não publicar automaticamente só porque uma fase foi concluída.

`frontend/package.json` é a fonte canônica de build; `frontend/package-lock.json`, `backend/pyproject.toml` e `backend/uv.lock` devem permanecer sincronizados. O bundle Vite incorpora a versão sem chamada à API. A versão OpenAPI continua independente. A versão implantada em `679e706` é `0.1.0`, usada como baseline histórico; `v0.2.0` já foi publicada. A anotação abaixo sobre o próximo candidato de múltiplas bibliotecas é histórica e deve ser atualizada conforme o conteúdo real da próxima publicação.

Preserve o mecanismo oficial existente, `scripts/release.py`: `prepare patch|minor|major` calcula e sincroniza o candidato nos metadados; repetir o comando mantém o candidato pendente. `validate` verifica sincronização e que a versão ainda não foi publicada. O workflow Deploy valida antes da migração e finaliza a tag anotada e a GitHub Release, com notas automáticas, somente depois dos dois deploys e da sondagem pública. Se houver falha, repita o mesmo candidato e SHA sem novo incremento; se a tag foi criada mas a Release falhou, repita `finalize`. Um rollback de código já publicado exige nova versão PATCH. Nunca mova tags nem reverta migrações automaticamente. Backup é uma rotina independente, não um gate de release. Enquanto Actions estiver pausado, siga os mesmos passos no processo manual; editar o workflow não reativa Actions.

### Alertas de dependências adiados

A auditoria desta worktree reportou 10 nós de pacotes afetados (8 moderados e 2 críticos). `npm audit --omit=dev` não reportou vulnerabilidades: os nós afetados são dependências de desenvolvimento/teste, não do bundle/runtime de produção. Os dois críticos estão no `tinypool` transitivo de `vitest@3.2.7` (`tinypool@1.1.1`): [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) trata de prototype pollution/opções de worker com impacto de execução de código; [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) trata de opções de `run()` com impacto de execução de código. A correção informada para `tinypool` é 2.1.2 ou posterior, exigindo atualização coordenada do Vitest.

Os moderados incluem dois problemas em `@vitest/mocker@3.2.7` — leitura arbitrária de arquivos via redirect mock ([GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)) e injeção de código por registro de mock via WebSocket do Vite ([GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8)) — e avisos de `glob` ([GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4)) e `minimatch` ([GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249)). O relatório também lista caminhos transitivos que carregam esses avisos, como `@vue/language-core`, `vue-tsc`, `@vue/test-utils`, `js-beautify` e `editorconfig`; por isso os dez nós afetados não significam dez vulnerabilidades independentes.

Criar tarefa posterior para atualizar Vitest/mocker e resolver o grafo transitivo com versões compatíveis, revisar o lockfile e repetir auditoria completa, testes e build. Até lá, não expor servidor Vite/HMR a clientes não confiáveis nem reativar execução pública de testes/CI sem tratar esses alertas. Não aplicar `npm audit fix` indiscriminadamente. Nesta revisão não foi identificada vulnerabilidade efetivamente explorável no runtime de produção.

Em falha de deploy, não finalize: repita o mesmo candidato e SHA sem novo incremento. Se a tag foi criada mas a GitHub Release falhou, repita `finalize`; a operação é idempotente. Um rollback de código já publicado exige novo PATCH. Nunca mova tags nem reverta migrações automaticamente.


## Publicação das Fases 3 e 4 — v0.7.0

Publicação manual autorizada pelo pedido de 20/11/2026, mantendo os workflows pausados. O PR de implementação [#29](https://github.com/marrcandre/julib/pull/29) foi integrado por squash; o PR de preparação de release [#30](https://github.com/marrcandre/julib/pull/30) também foi integrado por squash. Commit publicado: `a2f0c2b333dd59f6791f282c021edee67807efb5`. GitHub Release [v0.7.0](https://github.com/marrcandre/julib/releases/tag/v0.7.0) aponta para esse mesmo SHA.

### Backup e migration

Antes da migration, o artifact cifrado da [execução 44605863622](https://github.com/marrcandre/julib-backups/actions/runs/44605863622) foi confirmado disponível até 19/12/2026. SHA-256 `3067b1b606f5360b762fa18fc9577b2616942faacf25766de6708e2f76fc7b1f`, envelope v2, 371 mídias. `scripts/backup.py verify` confirmou autenticidade, hash e integridade; o restore foi repetido em PostgreSQL 17.11 descartável e a migration 0019 aplicou sem erro. Os arquivos descriptografados e o container temporário foram removidos depois do ensaio.

A `0019_book_bibliographic_metadata` é aditiva: adiciona `subtitle`, `description` e `subjects`; não faz backfill nem altera registros existentes. Em produção, `secure_database --role julib_app` foi executado antes e depois da migration; Django confirmou `0019` aplicada. Verificação somente de leitura registrou 379 livros antes e depois, zero linhas com os novos campos não padrão, RLS habilitado e policy `julib_backend_access` ativa para `julib_app`. Nenhum livro foi criado, editado ou enriquecido.

### Deployments e smoke tests

| Componente | Deployment Vercel | Estado | Commit e versão |
| --- | --- | --- | --- |
| Backend | `dpl_4gRxryo5Q43QXGPMw9AFXhchaqWW` | READY, produção | `a2f0c2b333dd59f6791f282c021edee67807efb5`, v0.7.0 |
| Frontend | `dpl_DfKxELETSn1n1JPUwnF4NHba5eiR` | READY, produção | `a2f0c2b333dd59f6791f282c021edee67807efb5`, v0.7.0 |

Frontend `/` e `/importar`, backend `/api/v1/health` e `/api/v1/health/ready`, e readiness pelo proxy do frontend responderam HTTP 200. O endpoint público de OpenAPI permaneceu HTTP 403, conforme a restrição existente. Como não há linhas com valores bibliográficos novos na produção, a exibição com dados reais não foi exercitada; a serialização e a UI estão cobertas pelos testes locais. Logs Vercel consultados no intervalo retido de 30 minutos após o deploy: 17 registros de runtime do backend e 1 do frontend, sem error/fatal.

GitHub Actions permaneceu pausado: `CI` e `Deploy` em `marrcandre/julib` e `Private manual backup` em `marrcandre/julib-backups` estão `disabled_manually`. `DEPLOY_ENABLED=false`. A validação local passou (`make check-local`: 319 backend, 1 ignorado, 61 frontend, build, Ruff, mypy e Django; `make e2e-local`: 43/43). Nenhum enriquecimento de dados de produção foi executado. Para uma biblioteca real, qualquer prévia não destrutiva deve continuar explícita por `--library`, seguir os limites dos provedores e não usar `--apply`; este pedido também determinou que não se execute comando de enriquecimento em dados reais nesta publicação.
