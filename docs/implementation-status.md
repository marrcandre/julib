# Entrega inicial — 04/11/2026

Este arquivo é um histórico cronológico: números e pendências das primeiras seções refletem o momento de cada registro. Para a situação consolidada e as lacunas ainda abertas, consulte a [verificação de requisitos de 05/11/2026](reviews/2026-11-05-requisitos-e-proximas-entregas.md).

## Implementado e verificado localmente

- Backend Django/Ninja, PostgreSQL e Admin/Swagger com controle de acesso.
- Biblioteca/participantes, catálogo/edições/exemplares, tags, locais e operação em lote.
- Pessoas, empréstimos/devoluções/perdas e preservação de histórico.
- Busca Google Books/Open Library, assinatura/verificação de mídia, importação Goodreads idempotente e consulta por link revogável.
- Interface Vue/TypeScript/PrimeVue, tipos gerados por OpenAPI, paleta Siloé, temas e PWA online.
- README, MIT, contribuição, operação, workflows CI/deploy e template privado de backup.
- Revisão independente apontou três problemas relevantes (imutabilidade da biblioteca no Admin, repetição segura de cadastro após perda de resposta e ISBN Excel vazio); corrigidos com testes reproduzindo cada caso.

Validação atual: 40 testes backend em PostgreSQL, 6 Vitest e 8 jornadas Playwright na CI; Ruff, mypy, build/tipos e checks de migrações aprovados. Upload e recuperação reais de mídia e restauração do artifact cifrado remoto conferidos.

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

## Prontidão para UptimeRobot — 04/11/2026

Implementada rota pública GET/HEAD /api/v1/health/ready com consulta de leitura a library_library, retorno 200/503 genérico e sem cache. /api/v1/health continua sem acesso ao banco. Conexão isolada limita conexão a 3s, consulta a 2s e espera por lock a 1s, usando SET LOCAL e rollback/fechamento. Testes reproduziram rota ausente e HEAD não suportado antes da implementação; cobrem banco saudável, falha sem vazamento de detalhes, lock real/recuperação e HEAD com o mesmo status. Supabase real respondeu à sondagem em 0,193s. Revisão focada sem bloqueios. Validação local: 40 backend, 6 frontend, Ruff/mypy, build/tipos e checks de migrações aprovados. Monitor externo deve apontar à nova rota, com intervalo de cinco minutos.

## Catálogo responsivo e origem das capas — 05/11/2026

Usuário confirmou criação do monitor UptimeRobot. Rota pública /api/v1/health/ready conferida com GET/HEAD: HTTP 200 e Cache-Control no-store, private. Deploy 41925175379 concluído com sucesso.

Catálogo passa a oferecer Cartões, Somente capas e Lista, com escolha salva no navegador. Grades usam cinco colunas no desktop e três no celular; lista exibe miniatura e informações ao lado. Disponibilidade é ícone com nome acessível e tooltip junto ao título; Emprestado só é usado quando exemplares privados confirmam empréstimo. Editor mostra a capa atual e sua atribuição quando aplicável. Sem imagem, modo capas mostra marcador com o título. Links de fonte continuam acessíveis; Google usa a imagem oficial com link, evitando texto redundante. Capturas desktop/móvel/editor conferidas; 6 Vitest, build/tipos e 8 Playwright aprovados. Revisão focada sem achados importantes.

As 67 capas continuam como referências externas. Usuário solicitou preparar cópia gerenciada, condicionada à verificação das fontes. Não foi identificada autorização geral para criar cópias permanentes dessas imagens: Google APIs Terms §5(e) condiciona cópias permanentes à autorização do titular ou lei aplicável; Open Library orienta servir imagens pela Covers API e não transfere os direitos individuais das capas. Nenhuma cópia automática para Cloudinary foi executada. Uploads fornecidos pelo usuário com direito de uso continuam gerenciados no Cloudinary e incluídos no backup. Atribuição pode decorrer dos metadados Google/Open Library mesmo quando a capa é substituída por upload próprio; Goodreads só ganha essa indicação quando a capa externa reconhecida determina a fonte.

Fontes verificadas: https://developers.google.com/terms#e-prohibitions-on-content ; https://developers.google.com/books/branding ; https://openlibrary.org/dev/docs/api/covers ; https://openlibrary.org/developers/licensing .


Publicação do catálogo concluída: CI 42019530236 e Deploy 42019721802 aprovados. Teste Chromium sobre a interface publicada, com dados fictícios restritos ao teste, confirmou colunas 5/3, três modos, persistência e capa no editor, sem escrever na coleção. GET/HEAD da rota de prontidão continuam respondendo 200 com no-store, private. Nenhuma capa foi copiada automaticamente para Cloudinary.

## Preferências do catálogo e busca — 05/11/2026

Somente capas passa a ser a primeira opção e o padrão, seguida por Cartões e Lista. No desktop, capas usam sete colunas por padrão, ajustáveis entre cinco e dez; no celular permanecem três. Modo e densidade são salvos por usuário na API autenticada, com proteção CSRF. Migração aditiva mantém defaults no banco para compatibilidade durante a publicação.

Busca automática após 400 ms de pausa, botão acessível para limpar e proteção contra respostas antigas substituírem resultados recentes. Detalhes exibem a capa atual à direita do envio de imagem, incluindo disposição móvel sem sobreposição. Testes cobrem persistência, isolamento entre usuários, validação, CSRF, inserções compatíveis com a versão anterior e comportamento visual/busca.

Publicação concluída pelo PR #6: CI 42024937166 e Deploy 42025168340 aprovados. Validação final: 43 testes backend, 6 Vitest, tipos/build e verificações estáticas; oito jornadas locais e teste focado sobre a interface publicada aprovados. GET/HEAD de prontidão retornam 200 e no-store, private. Conferência somente leitura preservou os 312 livros e 312 exemplares; usuários existentes receberam Somente capas/sete colunas. Backup automático concluído antes da migração.

## Controles compactos e capas em empréstimos — 05/11/2026

Controles de visualização exibem apenas ícones, preservando nomes acessíveis e dicas. Densidade de Somente capas aceita de três a dez colunas e vale em qualquer largura, com a mesma preferência por usuário. Busca automática reduzida a 300 ms, verificada com relógio controlado em 299/300 ms. Empréstimos no painel e na página própria exibem miniatura, origem quando aplicável e marcador para capa ausente ou falha de imagem. A API passa a incluir URL e atribuição sem consultas adicionais por empréstimo; migração apenas ajusta o validador mínimo da preferência.

Verificação local: 44 testes backend, 6 Vitest, Ruff/mypy, schema/tipos/build aprovados. Duas jornadas focadas conferem controles, persistência, densidade móvel, busca concorrente e miniaturas/fallback em desktop e celular.

PR #7 integrado e publicado: CI 42027697100 e Deploy 42027933166 aprovados, com backup anterior à migração. Ambas as jornadas focadas passaram também na interface pública, com dados fictícios interceptados pelo teste e sem escrever na coleção. GET/HEAD de prontidão responderam 200 com no-store, private.

## Páginas e últimas aquisições — 05/11/2026

Livros disponíveis deixam de exibir ícone de status; empréstimo/indisponibilidade continuam sinalizados. Últimas aquisições usa cinco capas clicáveis e consulta os cinco livros distintos mais recentemente adquiridos, considerando a aquisição mais recente quando há cópias repetidas. Mantém cinco colunas também no celular e a atribuição das fontes.

Número de páginas passa a ser opcional e positivo no modelo/API/admin, cadastro, edição, detalhes, catálogo público e lista. Google Books e importação Goodreads preenchem valores válidos; desconhecidos permanecem nulos. Migração aditiva e compatível com o backend anterior. Comando fill_goodreads_pages permite prévia e aplicação apenas em campos vazios, por biblioteca e ID Goodreads exato, sem criar registros nem sobrescrever dados conhecidos.

Validação local: 48 testes backend, 6 Vitest, verificações estáticas e tipos/build aprovados; jornadas focadas conferem cinco capas no painel, ausência de ícone disponível, indicação de empréstimo e páginas no editor/detalhes, em desktop/celular.

PR #8 publicado: CI da revisão 42030119139 e CI integrado 42030788306 aprovados. Execução duplicada do push 42030090017 cancelada enquanto instalava Chromium, após a revisão validar o mesmo commit. Deploy 42030979032 concluído com backup anterior à migração. Ambas as jornadas focadas passaram na interface pública com dados fictícios interceptados, sem alterar a coleção; GET/HEAD de prontidão retornaram 200.

Recuperação do CSV original em produção: prévia identificou 284 campos vazios com ID Goodreads exato e páginas válidas. Aplicação transacional preencheu os 284, preservando os 312 livros e 312 exemplares. Outros 28 permaneceram sem número de páginas conhecido; nenhum valor foi estimado.

## Verificação do cadastro por câmera — 05/11/2026

Teste com Chromium e vídeo sintético EAN-13 reproduziu consulta automática duplicada após selecionar um resultado: useCandidate liberava o scanner antes de salvar. Bloqueio agora persiste durante a revisão; Ler outro código permite nova tentativa explícita, e Salvar e continuar libera a próxima leitura. Validação de ISBN/prefixo/dígito verificador ignora códigos não correspondentes a livros. Controle da sessão encerra captura iniciada após o fechamento da janela.

Três testes com decoder real e câmera simulada cobrem leitura automática, ausência de cadastro antes de salvar, dados estáveis, nova tentativa, salvamento explícito, permissão negada com cadastro manual disponível e fechamento durante permissão pendente. Gerador Y4M padrão incluído no harness de CI, sem arquivos de vídeo no Git. Validação local: 48 backend, 7 Vitest, build/tipos e três jornadas de câmera aprovados. Ainda falta testar a câmera física no Poco F5/Samsung A34; simulação não verifica foco, luz ou permissão específica dos aparelhos.

PR #9 publicado: CI de revisão 42033635270, CI integrado 42035538576 e Deploy 42035855441 aprovados. Três jornadas da câmera passaram também na interface pública com vídeo sintético e API interceptada, sem escrever na coleção. Consulta externa real por isbn:9780261102217 retornou uma correspondência exata no Google Books. GET/HEAD de prontidão continuam 200 com no-store, private. A verificação física nos aparelhos permanece pendente.

Validação física confirmada pelo usuário em 05/11/2026 no Poco F5: câmera e buscas por nome, ISBN e título do livro funcionaram. Esta confirmação encerra a pendência da câmera nesse aparelho; a verificação no Samsung A34 permanece sem confirmação.

## Auditoria de requisitos — 05/11/2026

Confrontados desenho aprovado, decisões posteriores, código e workflows. Relatório em docs/reviews/2026-11-05-requisitos-e-proximas-entregas.md. Sondagens locais com dados sintéticos e rollback confirmaram ausência de aviso de duplicata sem ISBN, gestão parcial de tags/exclusões e lacunas de erro por linha/consulta de importação expirada. Backup e cleanup diários conferidos no workflow privado; marcações antigas de operação no plano foram consolidadas como concluídas. Nenhuma funcionalidade nem dado de produção foi alterado nesta auditoria.

## Login de Juliana validado — 05/11/2026

Após relato de tentativa sem sucesso, inspeção somente leitura confirmou conta ativa, identidade Google verificada e participação na biblioteca inicial. Havia login concluído em 04/11 às 20h09 (America/Sao_Paulo). Verificação pública atual confirmou prontidão/entrada Google HTTP 200, POST com CSRF redirecionando ao Google (302), callback correto e state presente. Registros recentes disponíveis não apresentaram erros/avisos correspondentes; o período antigo não estava retido. Não foi identificada nem corrigida uma causa para a falha anterior.

Usuário confirmou em 05/11/2026 novo login bem-sucedido com a conta da Juliana no celular dela. Pendência de login real encerrada; nenhuma alteração de código, autorização ou participação foi necessária. Convites continuam adiados por escolha explícita do usuário. O resultado não confirma ainda câmera ou instalação do PWA nesse aparelho.

Validação adicional confirmada pelo usuário em 05/11/2026: o celular da Juliana é um Samsung A34 e a câmera também funcionou. Login e câmera física estão validados nesse aparelho. Instalação/abertura como PWA ainda não foi confirmada.

## Busca de ISBN brasileiro — 05/11/2026

Reproduzida ausência dos ISBNs 9788570550156 e 9786583581112 no Google Books/Open Library, tanto digitados quanto com prefixo isbn: da câmera. Ambos válidos; leitura não era a causa. Consulta real BrasilAPI/CBL encontrou A Mensagem de 2 Timóteo e Solo, respectivamente. Primeiro retorna ISBN-10 equivalente; segundo informa 656 páginas. Nenhuma resposta trouxe capa.

Busca agora normaliza ISBN digitado/prefixado/com hífens, exige correspondência do identificador retornado e consulta BrasilAPI com providers=cbl como alternativa somente para ISBN. Sem copiar capas nem depender de nova credencial/plano pago. Origem BrasilAPI/CBL preservada no cadastro e exibida nos resultados/editor mesmo sem capa. Busca textual mantém o fluxo anterior. 54 testes backend, 7 Vitest, tipos/build e duas jornadas focadas aprovados; consultas reais dos dois exemplos encontraram os títulos pelo código novo.

Referências técnicas: https://developers.google.com/books/docs/v1/using ; https://github.com/BrasilAPI/BrasilAPI/blob/main/pages/api/isbn/v1/%5Bisbn%5D.js .

PR #10 publicado: CI 42066854800 e CI integrado 42067260763 aprovados; Deploy 42067571355 concluído com backup prévio. Duas jornadas focadas passaram na interface pública com respostas de API interceptadas pelo teste, sem gravar na coleção. Consulta real aos provedores com o código novo já havia confirmado ambos os ISBNs. GET/HEAD de prontidão responderam 200. Sem migração ou alteração dos livros existentes.

## Catálogo compacto aprovado — 05/11/2026

Implementação da prévia aprovada: header de 56 px e navegação móvel em drawer; título com badge numérico acessível; + agrupa câmera/busca/manual; menu secundário agrupa importação/organização/compartilhamento; filtros em rascunho com Aplicar/Limpar e chips; modos e slider 3–10 em painel. Avisos de sucesso transitórios, erros persistentes.

Densidade agora local por user_id e navegador/dispositivo, com padrão inicial quatro no celular/sete no desktop; não usa fingerprint nem sincroniza entre aparelhos. Modo de visualização permanece na conta. API legada de preferências continua compatível. Sessão inclui apenas o próprio user_id. GET autenticado de compartilhamento informa só active, sem gerar/revogar nem revelar token; geração e desativação são explícitas com confirmação. Token exibido somente no diálogo em que foi gerado, evitando reutilizar URL local possivelmente obsoleta. Sem migração de banco.

Verificação: 55 backend, 9 Vitest, Ruff/mypy/tipos/build, 14 jornadas E2E e inspeção visual móvel/desktop. Câmera e cadastro contínuo preservados; teste cobre controles, slider pelo teclado, preferências isoladas entre contas/contextos, filtros só ao aplicar e compartilhamento sem mutação ao abrir. Primeira capa em 187 CSS px na conferência móvel; sem overflow/erros JS. Revisão independente focada sem achados importantes.

PR #11 publicado: CI 42077866683, CI integrado 42078368422 e Deploy 42078669659 aprovados, com backup anterior. Seis jornadas sobre a interface publicada conferiram catálogo compacto, preferências por conta/contexto, compartilhamento por ações explícitas, câmera e busca ISBN, usando respostas de API interceptadas sem gravar na coleção. QA visual publicada: primeira capa móvel em 187 CSS px, sem overflow ou erros JS; GET/HEAD de prontidão 200 com no-store, private.

## Confirmações temporárias discretas — 05/11/2026

Confirmações de livros já usavam Toast com vida de 3,5 segundos, mas apareciam centralizadas horizontalmente e com apresentação maior. Ajustado para canto inferior direito, largura máxima 360 px e área segura móvel, tipografia/ícone/espaçamento compactos. Nova confirmação substitui a anterior, evitando acúmulo. Cópia bem-sucedida do PIX também passa a Toast; falha de cópia permanece junto da chave para orientar a ação manual. Avisos de progresso e recuperação continuam persistentes, pois não são confirmações transitórias.

Teste de navegador reproduziu o posicionamento anterior e passou com posição/tamanho/expiração de Dados atualizados no desktop e celular e expiração da confirmação PIX. 9 Vitest e tipos/build aprovados; revisão focada sem achados importantes. Nenhuma mudança de API ou banco.

## Publicação das confirmações temporárias — 06/11/2026

PR #12 integrado: CI 42080469241, CI da main 42080876738 e Deploy 42081189863 aprovados. Teste sobre a interface pública confirmou posição compacta no canto, desaparecimento automático após edição no desktop/celular e confirmação temporária do PIX, com API interceptada e sem gravar na coleção. Nenhuma migração foi necessária.

Usuário solicitou em seguida exclusão definitiva e livros desejados. Proposta em docs/superpowers/specs/2026-11-06-wishlist-deletion-proposal.md; regra para histórico de empréstimos foi perguntada e ainda aguarda resposta. A nova funcionalidade não foi implementada nesta etapa.

## Desejados e exclusão definitiva — 06/11/2026

Regra confirmada pelo usuário: bloquear exclusão quando houver qualquer histórico de empréstimo, inclusive devolvido. Implementados seletor compacto Acervo/Desejados, destino no cadastro por câmera/busca/manual, aquisição com localização/data, reclassificação explícita de registros elegíveis e exclusão com confirmação digitada. Desejados não criam exemplares, não contam no painel e não aparecem no link público. Histórico de exemplares anteriormente baixados permanece preservado.

A migração 0007 mantém todos os livros existentes no acervo, com default false também no banco. Referências técnicas de cadastro/importação passam a SET_NULL; recibos e resultados concluídos permanecem e bloqueiam recriação por retry. Fingerprints anteriores ao campo de destino são compatíveis. Aquisição, reclassificação, empréstimo e exclusão usam locks transacionais por biblioteca; empréstimos históricos continuam protegidos. Reversão do esquema faz preflight para não descartar desejados ou recibos.

Validação local: 64 testes backend, 9 Vitest e 17 jornadas Playwright; duas jornadas adicionais focadas em telas de 393/1280 px passaram, incluindo perda de resposta e retry da aquisição sem duplicar exemplar. Ruff, mypy, checks Django/migrações, build/tipos e git diff --check aprovados. Nenhum livro real foi excluído ou movido. Publicação e revisão final registradas no adendo a seguir quando concluídas.

### Publicação pendente por bloqueio externo do GitHub

PR #13: https://github.com/marrcandre/julib/pull/13, implementação no commit `600006d`. A CI https://github.com/marrcandre/julib/actions/runs/42212959255 foi recusada antes de iniciar o job: “The job was not started because your account is locked due to a billing issue.” Não é falha de testes; os checks locais acima passaram. GitGuardian não encontrou segredos. Não houve merge, migração nem deploy em produção. O usuário foi informado para verificar a conta, sem contratação de plano. Após liberação, reexecutar a CI do PR, integrar somente com sucesso e aguardar backup privado/migração/deploy do workflow normal.

QA visual isolada com API simulada também passou: primeira capa em 187 px no celular, sem overflow ou erro JavaScript; desejados omitem filtros físicos e o botão de excluir mostra bloqueio quando há histórico. Servidores locais de desenvolvimento restaurados nas portas 8000/5173.

Revisão independente focada concluída sem riscos importantes: isolamento/locks transacionais, preservação de empréstimos e recibos de idempotência conferidos. Plano atualizado com implementação/validação concluídas e CI/publicação explicitamente pendentes.

## Publicação manual autorizada — 06/11/2026

Após abrir chamado no GitHub, o usuário autorizou desativar temporariamente Actions e publicar manualmente. CI/Deploy no Julib e Private daily backup no privado foram desativados via CLI; arquivos preservados para retomada. Essa autorização substituiu o bloqueio operacional anterior, sem alterar plano, orçamento ou forma de pagamento.

PR #13 integrado com squash no commit `73ff09d67b57706d4d0fe943838bc8a2e07e0383`. Nova execução local completa passou: 64 testes backend, 9 Vitest e 17 jornadas Playwright, além de Ruff/mypy/checks Django/migrações/build/tipos. Revisão independente anterior sem achados importantes.

Backup pré-migração: release privado `manual-20261106T120246Z` em marrcandre/julib-backups, 7,598,510 bytes cifrados e 237 capas gerenciadas. SHA-256 `fe53b21086acbe1b063996a79ec31e53e1e74c437b89daf6403e003627ba19a5`. O arquivo foi baixado novamente, hash conferido e descriptografado; dump restaurado em PostgreSQL 17 descartável e contagens conferidas (322 livros, 322 exemplares, 1 pessoa, 1 empréstimo, 10 recibos), com os 237 arquivos de mídia presentes. Banco descartável removido ao terminar; cópia local cifrada preservada fora do repositório público.

Migração 0007 aplicada com proteção de tabelas antes/depois. Contagens preservadas, zero desejados após migração, 28 tabelas com RLS e nenhum grant público/anon/authenticated. Backend `dpl_FJaSrANmL5r5PhxF2qxS7FLTQiAj` e frontend `dpl_DHRxQP3WnXgg9t8Tg31Ay7Wvy1ur` publicados manualmente na Vercel, ambos READY. Frontend: https://julib.vercel.app. Backend: https://julib-api.vercel.app.

Verificação de produção: prontidão GET/HEAD HTTP200 sem cache, catálogo privado retorna401 sem autenticação e Swagger retorna403 ao visitante em ambas as origens. Apresentação do livro com empréstimo existente informa exclusão bloqueada. QA visual com APIs simuladas sobre o frontend publicado passou no celular/desktop: capas em187px, sem overflow ou erro JS, filtros físicos ocultos nos desejados e exclusão bloqueada quando há histórico. Nenhum livro real foi excluído, adquirido ou reclassificado durante os testes. Servidores locais 8000/5173 restaurados.

O backup diário automático está pausado enquanto Actions estiver desativado. Fazer backup antes de cada publicação manual e conferir releases `manual-*` com retenção operacional de sete dias; releases não expiram automaticamente. Procedimento completo e comandos de retomada em docs/operations.md. Não considerar CI remota aprovada nem backup diário reativado até execução real após resolução do chamado.

## Página própria de detalhes e edição — 06/11/2026

O usuário aprovou proposta e prévia, confirmou URL própria/nova aba e autorizou implementar. Rota privada `/livros/:id`, links reais no catálogo e painel e compatibilidade com URLs antigas `?livro=`. Ficha completa, capa e cartões de exemplares substituem a modal de detalhes; editor próprio na mesma página reúne metadados e capa. Cancelar descarta o rascunho como na prévia; navegação/fechar/atualizar com alterações exige confirmação. Login de sessão encerrada preserva destino do livro.

A seleção de capa fica local até Salvar. PUT compatível aceita cover_public_id opcional, verifica pertencimento/recurso e confirma dados e vínculo numa transação. URL externa diferente limpa o cover_id antigo. Validação falha não aplica edição parcial e retry reutiliza upload já concluído. API/Admin/Swagger e câmera de cadastro preservados; sem novas dependências nem migração.

Catálogo registra busca/filtros/página na query, com posição por navegação da aba e retorno validado para o próprio catálogo. Visualização/densidade mantêm as preferências anteriores. Exemplares têm edição de local/data, histórico com vazio explícito e baixa/reativação; desejados/aquisição idempotente/exclusão protegida preservados.

Validação: 66 testes backend, 11 Vitest, 21 jornadas Playwright, Ruff/mypy/Django/migrações/build/tipos e git diff --check aprovados. Inclui nova aba, recarga, retorno com query/rolagem, capa local/cancelar/salvar/retry, sessão encerrada, edição real de exemplar e bloqueio de exclusão após empréstimo devolvido. QA visual com APIs simuladas em1366/393/320px, temas, histórico e bloqueio de exclusão passou sem overflow/erro JS. Revisão independente questionou confirmação ao Cancelar; comparada com a prévia aprovada, manteve-se a ação explícita imediata e esclareceu-se o spec. Sem achado importante de integridade pendente.

Backup manual pré-publicação cifrado e restauração conferida já concluídos; publicação/evidências remotas serão registradas no adendo final. Actions continua desativado por autorização prévia do usuário.

### Detalhes/edição publicados e verificados

PR #14 integrado no commit `7116330d3a1d411cabea4811f352a750456cd8de`; GitGuardian aprovado. Publicação manual autorizada, sem migração. Backend `dpl_A6ckq5NAXVGZCfAtn3V6bt9uTXPH` e frontend `dpl_7fDPWGxdTrQgMNDk5wsjEvFT7u6R` READY na Vercel; página disponível a participantes autenticados em https://julib.vercel.app/livros/ID.

Backup `manual-20261106T131326Z` no repositório privado, 7,598,667 bytes cifrados, SHA-256 `c4245017172ddbe14f6fa66b668b5bfc3ac236315e31708144933cf83eb6234a`,237capas. Baixado, hash validado, descriptografado e banco restaurado em PostgreSQL17 descartável; contagens iguais e mídia presente. Banco temporário removido, cópia local cifrada fora do repositório público. Nenhum registro real alterado nos testes/publicação:322livros,322exemplares,1pessoa,1empréstimo,10recibos preservados.

Checks finais66backend/11Vitest/21Playwright aprovados. Sobre o frontend publicado, outras3jornadas com APIs simuladas passaram: URL direta/nova aba/recarga, retorno com filtros/página/rolagem, imagem local e cancelamento, retry sem novo upload e link de login com next. QA visual publicado em1366/393/320px, temas, histórico e exclusão bloqueada passou sem overflow/erro JS. Smoke de ambas as origens confirmou GET/HEAD de prontidão200 sem cache, dados privados401 sem login e Swagger403 ao visitante; RLS e ausência de grants públicos conferidos por leitura.

Servidores locais restaurados nas portas8000/5173. Actions e backup diário pelo GitHub continuam pausados; rotina manual com backup antes de publicar permanece vigente até resolução do chamado.

## Crédito da capa e prioridade de APIs — 06/11/2026

Problema relatado no livro 313: capa gerenciada no Cloudinary ainda acompanhada de crédito de provedor. A leitura final confirmou source vazio; esse campo não foi alterado. A apresentação passa a distinguir a origem bibliográfica da imagem atual. Separados cover_attribution (imagem atual) e metadata_attribution (dadosGoogle), com campos no schema e tipos gerados, sem migração. Créditos opcionais saem da interface; Google obrigatório é rotulado Dados bibliográficos/Capa e deduplicado quando o volume é igual.

O usuário revogou a desativação completa de GoogleBooks antes de qualquer modificação no acervo. Decisão vigente: OpenLibrary primeiro, BrasilAPI com CBL/MercadoEditorial depois para ISBN, Google por último. Capas priorizamOpenLibrary e mantêmGoogle como alternativa. Os4registrosGoogle e21URLs de capasGoogle auditados foram somente lidos e não serão removidos/reclassificados. Fonte interna e identificadores preservados.

Prova:74testesbackend,14Vitest,22Playwright e Ruff/mypy/Django/migrações/build/tipos aprovados. A revisão apontou JSONmalformado daOpenLibrary bloqueando fallback; RED→GREEN com4formas inválidas e handler corrigido. Caso313 calculado com novo código retorna ambos os créditos vazios, preservando capa e origem interna; novoE2E distingue Googlemetadados da capa própria. Testes passaram a usar chaveBooksAPIfictícia, evitando exposição da configuração real em diagnósticos. Nenhum segredo encontrado nos arquivos versionáveis na conferência local.

Backup pré-publicação restaurado e publicação manual em preparação; evidência final no adendo posterior. Actions permanece pausado.


### Publicação e conferência final dos créditos

PR #15 integrado em `4b2e19b96f4eacb20b7765d8a0b237183da5b9ee`, GitGuardian aprovado. Backend `dpl_BCNYVXjJqS37c3xvxBDLPK5fJsMs` e frontend `dpl_J1FSmCCTpaBR5D4HyFChjjUJodTB` publicados e READY. Sem migração ou reescrita do acervo. Nova chave Books API configurada privadamente no backend de produção e validada com HTTP 200, sem registrar seu valor.

Backup privado `manual-20261106T164742Z`: 7.620.104 bytes cifrados, SHA-256 `a550485f83dd05509417c9dc55a8ebb60bf29ad961f0590ceffa609fc463c57d`, 238 mídias gerenciadas. Arquivo remoto baixado, hash conferido, descriptografado e restaurado em PostgreSQL descartável antes da publicação.

Além dos 74 testes backend, 14 Vitest e 22 Playwright prévios, o cenário de créditos passou sobre o frontend publicado, usando APIs simuladas. Leitura real confirmou livro 313 com capa Cloudinary e ambos os créditos vazios; procedência interna preservada. Contagens mantidas: 322 livros, 322 exemplares, 1 pessoa, 1 empréstimo e 10 registros de cadastro. Ambas as origens responderam prontidão 200, livros privados 401 e Swagger 403 sem autenticação. Servidores locais nas portas 8000/5173 disponíveis. Actions e backup diário continuam pausados; publicação manual com backup permanece vigente.

### Incidente de salvamento da capa — livro 58

O usuário recebeu resposta inesperada ao salvar. Logs de produção identificaram `ReadOnlySqlTransaction` no `SELECT FOR UPDATE` do salvamento, também observado no livro 222. Causa operacional: diagnóstico privado executou `SET default_transaction_read_only = on` na conexão do pool de transações, deixando a sessão física em modo somente leitura. A sondagem de prontidão não detectava isso porque apenas consulta o banco.

Defaults de papel/banco estavam intactos e o servidor não estava em recuperação. Foi renovada a única sessão ociosa do papel `julib_app`, sem interromper transações ativas ou alterar dados. Nova conexão confirmou default `off`. Corrigido o diagnóstico privado para `SET TRANSACTION READ ONLY` dentro de `transaction.atomic()`; nova execução confirmou que o default permanece `off` após o bloco. O caminho real `services.edit_book` para o livro 58 executou com sucesso dentro de transação revertida; comparação de todos os campos antes/depois confirmou preservação integral. Sem mudança no código de produto, migração ou novo deploy. Validação final do envio pelo navegador fica a cargo da nova tentativa do usuário.

## Situações e ordenação do catálogo — 06/11/2026

Decisão aprovada: remover seletor Acervo/Desejados do cabeçalho e reunir Disponíveis, Emprestados, Desejados e Perdidos em um filtro de seleção múltipla. Padrão da página: disponíveis e emprestados; nenhuma situação selecionada inclui as quatro oferecidas. Vendidos/doados existentes permanecem nos dados e detalhes, sem novas opções de filtro. Não há campo único de status no livro: as situações são derivadas dos exemplares/empréstimos, com OR entre situações, sem duplicar edições, e localização/sem localização correspondem ao mesmo exemplar.

Ordenações: inclusão recente (padrão)/antiga, título A–Z/Z–A, primeiro autor A–Z, aquisição recente/antiga e publicação recente/antiga. Aquisição usa a maior data de aquisição dos exemplares do livro, inclusive os anteriores; publicação aceita ano numérico de quatro dígitos. Dados ausentes ficam no final; desempate por identificador mantém paginação estável. Ordenação lembrada por conta/navegador, URL explícita tem prioridade. Filtros, ordem e página voltam junto com o catálogo ao sair dos detalhes; links antigos são traduzidos. Parâmetros antigos scope/available da API continuam suportados para clientes anteriores; a página nova usa statuses/order explicitamente. Sem migração nem reescrita de registros.

A revisão identificou a preferência sendo perdida em navegação interna para /livros e a exclusão indevida de exemplares antigos perdidos de livros posteriormente movidos a desejados. Ambos corrigidos, com cobertura de navegação interna e sobreposição desejado/perdido. O primeiro teste móvel detectou instabilidade do popup de seleção múltipla; quatro caixas de seleção dentro do painel de filtros resolveram o problema sem adicionar controles permanentes à tela. Evidência final de testes e publicação abaixo após conclusão.


### Situações e ordenação publicadas

PR #16 integrado em `b0a8aca2c7340ded98ac01dea5e8005726803b46`, GitGuardian aprovado. Backend `dpl_84fEQRMToJfYGxJeBpg7fUacpsFj` e frontend `dpl_Dc76pvr33px56xrVFTcxpoLexxcJ` READY. Sem migração ou alteração do acervo.

Validação: 78 testes backend, 17 Vitest e 24 Playwright aprovados; Ruff, mypy, Django, ausência de migrações, schema, tipos e build passaram. Primeira execução completa perdeu os processos do runner; repetição em processo independente concluiu as 24 jornadas. Sobre o frontend publicado, mais duas jornadas com APIs simuladas passaram em 320/1280 px, cobrindo situações, ordenação, preferência, navegação interna e retorno dos detalhes; sem overflow ou erro JavaScript. Leitura do PostgreSQL real executou quatro combinações de situações com nove ordenações sem duplicatas. Todas as consultas ficaram em transação explicitamente somente leitura; fora dela, default_transaction_read_only confirmou off. Livros/exemplares/pessoas/empréstimos/recibos continuam em 322/322/1/1/10. Ambas as origens: prontidão 200, catálogo privado 401 e Swagger 403 sem login.

Backup `manual-20261106T173040Z`, 7.627.346 bytes cifrados, SHA-256 `d69bd0ed744c50a1361fb4bf9f0d7123e70e3079a470dd837bd97bfa14b602e4`, 239 mídias gerenciadas; remoto baixado, hash validado e restauração descartável concluída antes de publicar. Servidores locais 8000/5173 restaurados. Actions e backup diário permanecem pausados, conforme autorização anterior.

## Paginação numerada e linhas por página — 06/11/2026

Aprovada paginação com números, reticências e intervalo exibido, no rodapé; tamanhos por linhas em capas/cartões (3/5/8/10, padrão 5), tamanho próprio em lista (24/48/96). Capas multiplicam pelas colunas escolhidas; cartões respeitam as 5 colunas desktop e 3 móveis existentes. Preferências de linhas/lista ficam por conta/navegador, independentes de ordenação e densidade. URL registra tamanho efetivo para interpretar a posição ao abrir/voltar dos detalhes em outra largura.

API privada passa a aceitar page_size entre 1 e 100, padrão legado 24, e ajusta a página à última existente quando filtros/exclusão deixam o número fora do intervalo. Nenhuma migração ou reescrita de dados. Paginação inclui links nativos (nova aba/teclado), estado atual acessível, histórico de navegação e ocultação dos controles para uma página. Troca de página leva ao início dos resultados; mudança de layout mantém um livro de referência na página recalculada.

As três solicitações adicionais de edição/toasts/capa ficaram registradas em docs/backlog.md para a próxima etapa, sem alteração desses fluxos nesta entrega.


### Paginação publicada e conferida

PR #17 integrado em `90af72072852ac006a2c00e5238786c1d3059638`; backend `dpl_8nGBhgH1KCdJAp8CXTBVuKmyHcwM` READY. A conferência visual final detectou herança da cor clara do cabeçalho nos links da paginação: contraste 1,41 no tema claro. Teste RED/GREEN e estilo local `color: var(--ink)` corrigiram o problema, com revisão focada. PR #18 integrado em `d628489058ded0494d91becfdf82416708f3c640`; frontend final `dpl_CdbRv9NYXcS7aB2T318pu3JK1M8w` READY. GitGuardian aprovado nos dois PRs. Nenhuma migração ou reescrita do acervo.

Validação base: 79 testes backend, 21 Vitest, 27 Playwright, Ruff/mypy/Django/schema/tipos/build. Patch de contraste: três jornadas focadas e build aprovados; mais três jornadas com APIs simuladas sobre o frontend publicado passaram em móvel/desktop, incluindo contraste mínimo 4,5, retorno dos detalhes, histórico, linhas/lista e resize. Leitura do catálogo real conferiu oito tamanhos entre 15 e 100, ajuste da última página, resultado vazio e ausência de duplicatas, sem gravações. Contagens iguais ao backup: 323 livros, 323 exemplares, 1 pessoa, 1 empréstimo e 11 recibos de cadastro. A inspeção ficou em transação explicitamente somente leitura e confirmou default de escrita intacto ao terminar. Ambas as origens responderam prontidão 200, catálogo privado 401 e Swagger 403 sem login.

Backup privado `manual-20261106T181915Z`, 8.015.771 bytes cifrados, SHA-256 `53045dfd0982ac959617f207bd6a588aaa94845541f150ee7e0ae674c095110d`, 248 mídias gerenciadas: remoto baixado, hash validado e restauração descartável concluída antes desta publicação. O mesmo backup foi utilizado na conclusão do ajuste visual da entrega. Servidores locais 8000/5173 restaurados. Actions e backup diário continuam pausados conforme autorização anterior. Próximos ajustes de edição/toasts/capa permanecem em docs/backlog.md.
