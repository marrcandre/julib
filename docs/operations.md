# Operação do Julib

Estado inicial: aplicação local e workflows em implementação; serviços externos e cópias reais ainda não ativados. Use os testes e o registro de entrega para conhecer a validação atual.

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

URI de retorno local usando o proxy: `http://127.0.0.1:5173/accounts/google/login/callback/`. Produção: `https://SEU_FRONTEND/accounts/google/login/callback/`. A origem pública deve estar nos hosts/CSRF Django. Não coloque o domínio do backend como callback se a sessão for utilizada pela origem frontend.

O link de entrada abre a confirmação OAuth do allauth. Somente e-mail verificado em allowlist é aceito; as contas são ligadas à biblioteca inicial. Valide com os dois usuários reais e uma conta recusada antes de usar o sistema.

## Cloudinary

Configure CLOUDINARY_URL ou CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET apenas no backend. O SDK prioriza as variáveis individuais quando CLOUDINARY_CLOUD_NAME está preenchida; use um único formato para evitar misturar contas. A API assina upload na pasta da biblioteca; frontend envia arquivo diretamente para Cloudinary e solicita vínculo ao livro. Servidor consulta a mídia para validar origem e tamanho final. Limite da aplicação: 5 MB e imagens JPEG/PNG/WebP; configure também os limites de upload disponíveis na conta para conter originais muito grandes. Segredos nunca vão ao cliente.

Capas das APIs externas permanecem como URLs da fonte. Respeite os termos de Google Books/Open Library e atribua a fonte quando necessário. Nada de scraping de Goodreads.

## Vercel e CI/CD

Dois projetos a partir do mesmo repositório: root directory backend e frontend. Não ativar auto deploy por push nem previews com acesso à produção. O workflow Deploy depende de CI bem-sucedida no mesmo commit da branch main e de DEPLOY_ENABLED=true.

Frontend: build `npm run build`, output `dist`. Gere rewrites com `BACKEND_ORIGIN=https://SEU_BACKEND uv run python scripts/configure_frontend.py` a partir da raiz. O arquivo frontend/vercel.json é gerado e ignorado. Backend: entrypoint config/wsgi.py e collectstatic; migrations são executadas separadamente no workflow. Teste a integração de cookies/redirects/Swagger no deploy.

Secrets no GitHub: VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_BACKEND_PROJECT_ID, VERCEL_FRONTEND_PROJECT_ID, MIGRATION_DATABASE_URL, DJANGO_SECRET_KEY. Variáveis: BACKEND_ORIGIN, APP_ORIGIN e DEPLOY_ENABLED. Configure também BACKUP_REPOSITORY e BACKUP_DISPATCH_TOKEN (acesso apenas ao Actions do repositório privado): o deploy pede uma cópia nova e aguarda sucesso antes de migrar. Os envs de runtime (Google/Cloudinary/banco/allowlist etc.) ficam nos projetos Vercel. Crie o environment production com os controles desejados e serialização.

Antes de habilitar DEPLOY_ENABLED: CI remota verde, Google validado, Data API protegida, backup privado ativo/restaurado, migrações revisadas como compatíveis e cotas verificadas. Não faça migrações destrutivas automaticamente. O workflow exige backup privado bem-sucedido imediatamente antes de migrar; a primeira ativação exige configurar e testar essa integração.

Falha de backend interrompe publicação do frontend. Rollback do código só com schema compatível; recuperação do banco é deliberada e precisa de destino revisado. O workflow não desfaz migrações automaticamente.

## Backup privado diário

Mantenha o código num repositório público e o workflow operacional em repositório privado. Copie ops/backup-workflow.yml.example para `.github/workflows/backup.yml` **somente no privado**. O job recusa repositório público. Agenda UTC 06:23 (03:23 em São Paulo), também com execução manual.

Gere chaves localmente:

```sh
uv run --project backend python scripts/backup.py keygen --private /CAMINHO_SEGURO/julib-private.pem --public /CAMINHO_SEGURO/julib-public.pem
```

Guarde a chave privada fora do GitHub e uma segunda cópia segura. A chave pública PEM entra no secret BACKUP_PUBLIC_KEY do repositório privado. Outros secrets: BACKUP_DATABASE_URL e credenciais Cloudinary. DATABASE_URL para leitura das referências aponta para o mesmo banco. Ajuste a referência do código no workflow ao commit/branch revisado.

O script gera dump PostgreSQL custom sem owner/ACL e pacote das capas gerenciadas, manifesto e arquivos, cifrado por AES-256-GCM com chave aleatória protegida pela chave pública RSA. Não copia capas externas indisponíveis; guarda suas URLs no banco. Não faz upload parcial nem envia cópia sem cifrar. O limite inicial de pacote é 50 MB; sete pacotes usam até aproximadamente 350 MB, fora outros consumos. Confirme cotas reais no GitHub/Supabase/Cloudinary; a política de inatividade não é SLA. O cliente pg_dump deve ser da mesma versão principal ou mais recente que o servidor.

Retenção de sete dias configurada no artifact privado. O job falha ao exceder o orçamento; não marque “backup completo” se falhar. Deduplicação de mídia e migração para outro destino são próximos passos caso a medição ultrapasse a cota; não estão ativadas silenciosamente. Esse impedimento precisa ser resolvido antes de usar o acervo real em volume incompatível.

## Testar recuperação

Baixe o artifact privado e extraia apenas o arquivo .enc. Descriptografe localmente:

```sh
uv run --project backend python scripts/backup.py decrypt --private /CAMINHO_SEGURO/julib-private.pem --input /CAMINHO_SEGURO/julib-backup.enc --output /CAMINHO_SEGURO/julib-restore.tar.gz
```

Em diretório vazio e privado, liste o tar antes de extrair: contém database.dump, manifest.json e media/. Nunca aceite tar de fonte desconhecida. Restaure em banco **novo e descartável**, nunca na produção durante um teste:

```sh
pg_restore --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL" database.dump
```

Confira contagens de livros/exemplares/pessoas/empréstimos, relações, estados e imagens conforme manifesto. Para perda da conta Cloudinary, reenviar mídia conforme manifesto e atualizar IDs/URLs nos livros, mantendo correspondência por public_id. Essa migração requer validação manual; não confundir dump restaurado com restauração das imagens concluída. Confirme as duas contas Google e revogue links antigos se houver incidente.

Registre tamanho, hora da última cópia e resultado do teste. Ative notificações de falha do Actions na conta de Marco. Agenda pode atrasar; execução manual e conferência periódica continuam disponíveis. Perda máxima depende da última cópia bem-sucedida, não apenas da agenda diária.

## Rotina

- Conferir consumo e suspensão/inatividade dos planos gratuitos.
- Conferir backup diário e executar teste de recuperação após alterações do mecanismo.
- Executar `cleanup_imports` diariamente (pode ser adicionado ao workflow operacional com conexão privada), removendo sessões após sete dias sem apagar livros.
- Não registrar contatos, tokens compartilhados ou conteúdo CSV em logs.
- Validar câmera e instalação do PWA nos Chrome do Poco F5 e Samsung A34. Automação em Chromium não substitui teste da câmera física.
