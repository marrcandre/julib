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

## Exclusividade do login Google — 04/11/2026

O formulário padrão /accounts/login/ ainda permitia solicitar código por e-mail e tentou conectar ao SMTP inexistente. Ativado SOCIALACCOUNT_ONLY, removendo o formulário local e as rotas de cadastro/recuperação de senha. ACCOUNT_EMAIL_VERIFICATION=none evita confirmação SMTP redundante; GoogleAdapter continua exigindo e-mail verificado pelo Google e presente na lista autorizada. Regressão verifica login Google disponível, ausência de campos locais, POST local bloqueado, rotas removidas e nenhum e-mail enviado.

## Tema e apresentação do login — 04/11/2026

Após o primeiro login Google confirmado pelo usuário, o seletor de tema foi simplificado para um botão com sol/lua e duas opções: claro e escuro. No primeiro acesso utiliza o sistema (escuro como fallback); a escolha explícita é persistida e não muda automaticamente. Esta decisão substitui o seletor anterior com opção Sistema.

Layouts allauth receberam cabeçalho, cartão central responsivo, fonte Inter local com licença, paleta Siloé nos dois temas e rodapé Julib. O login comum apresenta apenas o acesso Google. A confirmação mantém POST e CSRF. O tema acompanha a navegação entre Vue e autenticação pelo armazenamento da mesma origem. Teste Chromium móvel verifica alternância, persistência entre páginas, CSS carregado e ausência de overflow; os testes OAuth continuam passando. Inspeção visual de capturas clara/escura concluída. Login real foi confirmado pelo usuário antes deste ajuste visual.

## Foto Google na barra — 04/11/2026

Sessão inclui avatar_url obtida da conta Google autenticada, sem expor demais dados do provedor. Barra mostra foto circular e mantém iniciais se não houver foto ou o carregamento falhar. OpenAPI/tipos atualizados. Conta real local possui foto no perfil; teste de API cobre ausência/presença e teste Chromium cobre imagem válida/falha. Validação geral: 30 backend, 6 frontend, build/checks/tipos aprovados; teste de navegador da foto aprovado. CI remota anterior aprovada no commit 49043f1. Próxima integração: Cloudinary, aguardando configuração privada.

## Configuração Cloudinary por URL — 04/11/2026

CLOUDINARY_URL fornecida pelo usuário no .env privado. Aplicação aceita URL ou variáveis individuais usando a precedência nativa do SDK; assinatura utiliza configuração resolvida, sem devolver o segredo. Backup de mídia utiliza o mesmo configure. Teste de regressão cobre configuração apenas por URL e segredo ausente da resposta. Ping autenticado real do Cloudinary aprovado; nenhum ativo dos outros projetos foi modificado. Upload e recuperação reais de mídia continuam pendentes de validação.

## Validação real de mídia Cloudinary — 04/11/2026

Validado com imagem PNG sintética de 64×96 (88 bytes), sem dados pessoais ou alteração de livros: upload HTTP multipart usando os parâmetros assinados pela aplicação (mesmo protocolo do frontend), verificação de propriedade/formato/tamanho por verify_upload e entrega CDN HTTP 200. Conteúdo baixado foi cifrado/decifrado pelas funções reais de backup; SHA-256 conferiu. Conteúdo recuperado foi reenviado a um novo ID exclusivo de teste no prefixo da biblioteca, verificado e entregue com igualdade de bytes. Ambos os ativos criados foram removidos com sucesso; nenhum ativo de outros projetos foi alterado.

Isso valida o caminho de mídia e as primitivas de recuperação; não substitui o teste completo de backup de produção com dump, manifesto e restauração. Agenda privada continua desativada até configurar chaves, segredos e verificar cotas. Cliente OAuth confirmado com a conta de Marco; acesso de Juliana e validação nos aparelhos ainda pendentes.

## Preparação da primeira publicação — 04/11/2026

Conta Vercel Hobby verificada; projetos julib e julib-api criados, com destinos julib.vercel.app e julib-api.vercel.app. Runtime configurado apenas com segredos de produção; sem vínculo Git que publique antes da CI. Credenciais locais e de produção separadas.

Backup real do Supabase cifrado (15.492 bytes) e restaurado em PostgreSQL local descartável. Uma biblioteca, zero livros/exemplares/pessoas/empréstimos; contagens idênticas. Ajustado dump para public, excluindo extensões/esquemas internos do provedor. Restauração exige public vazio e role julib_app existente para políticas RLS. Chave privada local fora do código em ~/.local/share/julib/recovery; usuário deve manter segunda cópia segura. Template privado usa pg_dump17 em Docker e aceita CLOUDINARY_URL.

## Backup privado ativo e ajustes do proxy de produção — 04/11/2026

Workflow diário ativado somente em marrcandre/julib-backups, com referência de código fixa 3161b64 e retenção de sete dias. Execução 41909069606 aprovada; artifact cifrado remoto (15.490 bytes) baixado e restaurado no banco descartável, com contagens idênticas. Token restrito fornecido pelo usuário conseguiu solicitar e acompanhar outra cópia (41909740489). Secrets de deploy e environment production preparados. Cloudinary Free: 0,15 de 25 créditos usados na conta compartilhada no momento da conferência.

Primeiros deploys manuais backend/frontend executados após CI. Vercel exigiu entrypoint explícito config.wsgi:app, declarado no pyproject. Verificação pública encontrou API/estilos funcionais e 404 nas rotas com barra final; regras explícitas de accounts/admin preservam a barra. APP_ORIGIN fixa a origem pública para OAuth atrás do proxy e valida o Host recebido antes da canonicalização. Regressão OAuth falhou antes e passou após a correção; revisão independente focada sem achados importantes.

CSV Goodreads local detectado (451 registros) e excluído do Git. Nenhum registro importado automaticamente: seleção de livros possuídos permanece com o usuário.
