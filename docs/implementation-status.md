# Entrega inicial — 04/11/2026

## Implementado e verificado localmente

- Backend Django/Ninja, PostgreSQL e Admin/Swagger com controle de acesso.
- Biblioteca/participantes, catálogo/edições/exemplares, tags, locais e operação em lote.
- Pessoas, empréstimos/devoluções/perdas e preservação de histórico.
- Busca Google Books/Open Library, assinatura/verificação de mídia, importação Goodreads idempotente e consulta por link revogável.
- Interface Vue/TypeScript/PrimeVue, tipos gerados por OpenAPI, paleta Siloé, temas e PWA online.
- README, MIT, contribuição, operação, workflows CI/deploy e template privado de backup.
- Revisão independente apontou três problemas relevantes (imutabilidade da biblioteca no Admin, repetição segura de cadastro após perda de resposta e ISBN Excel vazio); corrigidos com testes reproduzindo cada caso.

Validação atual: 36 testes backend em PostgreSQL e 6 Vitest localmente; última CI com 7 jornadas Playwright; Ruff, mypy, build/tipos e checks de migrações aprovados. Upload e recuperação reais de mídia e restauração do artifact cifrado remoto conferidos.

## Produção

- Aplicação: https://julib.vercel.app — login Google privado para as contas autorizadas.
- Backend: https://julib-api.vercel.app — a interface encaminha API, autenticação, Admin e estilos pela mesma origem pública.
- Código público MIT: https://github.com/marrcandre/julib; PRs #1 e #2 integrados à main.
- Supabase Julib na organização IFC, sa-east-1, plano gratuito; runtime julib_app com permissões limitadas e RLS.
- Cloudinary Free compartilhado com outros projetos, usando prefixo julib/; autenticação, upload, entrega e recuperação verificados.
- Backup diário cifrado em https://github.com/marrcandre/julib-backups, privado, retenção de sete dias. Artifact real restaurado em banco descartável e contagens conferidas.
- CI/CD: CI na main e publicação posterior condicionada a backup privado bem-sucedido. Evidência da primeira execução automática ao final deste documento.
- Prévia Goodreads #1 com 451 registros pronta para seleção; a preparação não criou livros ou exemplares. CSV pessoal ignorado pelo Git.
- Chave privada de recuperação guardada localmente fora do GitHub em ~/.local/share/julib/recovery/julib-private.pem; mantenha segunda cópia segura.

## Validações e limites restantes

- Confirmar uso com a conta da Juliana e câmera/instalação PWA nos aparelhos Poco F5/Samsung A34.
- Selecionar somente os livros possuídos e conferir o resultado da importação antes de organizar localizações e exemplares duplicados.
- Snapshots completos de mídia têm limite de 50 MB por pacote. Caso a coleção de uploads exceda esse limite, implementar/validar deduplicação ou outro destino privado gratuito antes de ampliar o volume; nunca reduzir silenciosamente a cobertura.
- Três alertas GitGuardian históricos referem-se a valores sintéticos de CI/Docker/teste de TLS, conforme registro abaixo; nenhum corresponde a segredo real de produção.

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

## Verificações públicas e alertas de credenciais — 04/11/2026

Deploys após CI: frontend/backend públicos, confirmação Google HTTP 200 e POST 302, callback exato no frontend, página Google sem redirect_uri_mismatch/invalid_client e cookie CSRF Secure. API de sessão anônima retorna 401 e OpenAPI restrito retorna 403. Prévia Goodreads #1 criada com 451 linhas e zero livros/exemplares; usuário ainda escolhe os possuídos.

GitGuardian do PR #1 sinalizou três valores sintéticos: senha ci-only em workflow CI, senha julib-local-only no Compose ligado a loopback, e test:test@db.example.supabase.co no teste de preservação de TLS. Nenhuma credencial de produção corresponde aos alertas; não houve rotação de credenciais reais nem reescrita de histórico. Os avisos podem ser classificados como testes no painel GitGuardian. Deploy automático foi interrompido durante a investigação.

A rota raiz /admin/ precisava de regra exata antes das regras de subcaminhos, para não gerar barra duplicada no upstream. As rotas não vazias de autenticação já estavam respondendo corretamente.


## Primeira entrega automática — 04/11/2026

CI da main 41911780882 e Deploy 41913306145 concluídos com sucesso, incluindo cópia privada prévia, migrações compatíveis, backend e frontend Vercel e verificação pública. Chromium teve uma tentativa de instalação lenta no runner; o job repetido passou. Conferência Chromium móvel na produção: tema persistido entre SPA e login, cartão com CSS e nenhum erro JavaScript. Admin sem loop de redirecionamento. Uma conta Google e sua participação na biblioteca foram verificadas em produção, sem expor dados pessoais.

## Busca de capas dos livros importados

Comando enrich_covers busca apenas capas ausentes, por biblioteca, sem modificar source/source_id do Goodreads nem sobrescrever capas. ISBN é prioritário; sem ISBN exige título/autor correspondentes e resultado sem ambiguidade. Imagens são verificadas antes de vincular a URL da fonte; não são copiadas para Cloudinary. A atribuição considera a origem da capa mesmo quando os metadados vieram do Goodreads. Google Books retornou 429 em consultas anônimas; suporte a GOOGLE_BOOKS_API_KEY disponível apenas no servidor, com fallback Open Library. A aplicação da localização Escritório (Apto) aguarda o aviso do usuário de término da importação.

Revisão das capas identificou redirecionamento de imagem sem validação do destino. Teste reproduziu acesso a host não confiável; verificação de imagem passou a recusar redirecionamentos, com regressão aprovada.

## Capas vinculadas e localização preparada — 04/11/2026

GOOGLE_BOOKS_API_KEY fornecida pelo usuário, restrita à Books API, validada com HTTP 200 e configurada como segredo do runtime Vercel. PR #3 integrado; CI 41918569643 e Deploy 41918809559 concluídos com sucesso. Validação atual: 36 backend, 6 Vitest e 7 jornadas Playwright.

Rodada de busca concluída sobre os 312 livros importados nesse momento: 67 capas externas verificadas e vinculadas, 245 sem correspondência segura. Atualização condicional preservou ISBN/título/autores e identidade Goodreads, sem substituir capas existentes. Atribuição das fontes conferida em registros reais. URLs externas não foram copiadas para o Cloudinary.

Localização Escritório (Apto) criada. Nenhum exemplar foi movido ainda: o usuário informou que avisará ao finalizar a importação. Aplicar a localização a todos os exemplares após esse aviso e buscar capas apenas de eventuais livros novos que ficaram fora desta rodada.

## Importação concluída e localização inicial — 04/11/2026

Usuário confirmou o término com 312 livros. Contagens reais conferidas antes da alteração: 312 livros e 312 exemplares. Atualização transacional aplicou Escritório (Apto) aos 312 exemplares; conferência posterior confirmou todos nessa localização. As 67 capas existentes foram preservadas. Nenhum livro adicional ficou fora da rodada de capas. Backup privado pós-importação solicitado para registrar esse estado.
