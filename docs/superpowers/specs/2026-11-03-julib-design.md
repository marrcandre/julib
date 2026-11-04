# Julib — requisitos e arquitetura da primeira versão

Data: 3 de novembro de 2026. Autor do projeto: Marco André Mendes.

**Estado: aprovado para implementação em 04/11/2026, após revisão e alterações do usuário.** O levantamento original permanece em `docs/discovery/2026-11-03-biblioteca-pessoal.md`. Este documento substitui as pendências históricas já resolvidas naquele registro.

“Confirmado” indica uma decisão da conversa. “Proposta técnica” indica uma escolha do assistente submetida à aprovação deste documento. Valores operacionais e versões exatas serão fixados no plano e nos lockfiles, após verificar compatibilidade.

## 1. Intenção e critérios de sucesso

Organizar a biblioteca pessoal compartilhada de Marco e Juliana Mendes, com aproximadamente 1.000 exemplares distribuídos entre casa e trabalho. Priorizar cadastro gradual eficiente pelo celular, localização dos exemplares e controle confiável de empréstimos. O usuário deseja intervir pouco no frontend; usar convenções claras e componentes prontos.

O nome Julib reúne Ju, de Juliana, e lib, de biblioteca. A página Sobre contará essa homenagem.

A primeira versão será bem-sucedida quando:

- Marco e Juliana acessarem a mesma biblioteca com suas contas Google e puderem gerenciar o acervo.
- Livros puderem ser cadastrados manualmente, por busca, câmera e importação selecionada do Goodreads.
- Cópias idênticas puderem ter localizações e empréstimos independentes.
- A localização puder chegar à prateleira e ser atribuída em lote.
- Empréstimos, devoluções, atrasos e perdas preservarem histórico correto.
- Amigos consultarem um catálogo somente leitura por link revogável, sem dados privados.
- Admin, Swagger, testes, deploy condicionado à CI e recuperação de backup funcionarem.
- A operação inicial respeitar exclusivamente planos gratuitos.

Falhas a evitar: confundir livros lidos com possuídos, duplicar exemplares silenciosamente, expor contatos/localizações pelo link público, perder histórico ao dar baixa e publicar alterações sem CI aprovada.

## 2. Escopo e limites

### Confirmado na primeira versão

Catálogo por edição e exemplares; busca por título/autor/ISBN e filtros por tags livres; câmera em cadastro contínuo; cadastro manual sem ISBN; tags livres; hierarquia de locais; pessoas; empréstimos e histórico; importação Goodreads com revisão; painel inicial; link de consulta; capas por API e upload; temas claro/escuro; Sobre com PIX e links para Dons e Cinco Ministérios; Admin e Swagger; monorepositório público MIT; TDD e CI/CD; backup diário do banco por sete dias.

### Inclusões consolidadas na autorização de implementação

PWA instalável que depende de internet, sem sincronização offline. Incluído na autorização de implementação do desenho. Cópia diária das capas gerenciadas integra a estratégia de backup, sujeita à configuração e medição das cotas.

### Fora da primeira versão

Histórico/progresso de leitura, avaliações, categorias hierárquicas, preço/local de compra, marcação de não emprestável, notificações de atraso, reservas/solicitações pelos visitantes, convites e cadastro aberto, múltiplos papéis de gestão, histórico de prorrogações, etiquetas físicas e funcionamento offline. Sem homologação online.

A estrutura comportará bibliotecas e participantes separados, mas a versão inicial provisiona uma única biblioteca. Não haverá interface para criar outras bibliotecas, transferir propriedade ou excluir uma biblioteca inteira.

## 3. Abordagens discutidas e escolhidas

| Decisão | Escolhida | Alternativas e motivo |
| --- | --- | --- |
| Repositório | Um monorepositório público | Dois repositórios separariam administração, mas exigiriam coordenar PRs de API e interface. Usuário escolheu um. |
| Frontend | Vue + TypeScript + PrimeVue | React + PrimeReact também atende; Vue preserva preferência inicial com componentes ricos. Não se presume superioridade universal para agentes. |
| Backend | Django + Django Ninja + uv + anotações Python | DRF oferece serializers/viewsets; Ninja favorece schemas tipados e OpenAPI. FastAPI exigiria redefinir peças já fornecidas por Django. Usuário escolheu Ninja. |
| Navegação | Menu superior | Menu lateral acomoda mais opções, mas reduz área do conteúdo. Usuário aprovou superior no protótipo. |
| Infraestrutura | Vercel, Supabase PostgreSQL, Cloudinary | Vercel também oferece Blob e integra outros bancos. Cloudinary/Supabase são escolhas, não exigências da plataforma. |
| Ambientes | Local/CI e produção | Homologação online adiada por escolha do usuário. |

## 4. Pessoas, autenticação e isolamento

**Confirmado:** login Google individual; os dois e-mails serão previamente autorizados. Outras contas serão recusadas. Ambos têm gestão completa de livros, exemplares, tags, locais, pessoas e empréstimos. Só Marco acessa Admin e Swagger em produção. Convites ficam para depois.

**Proposta técnica:** autenticação Google via django-allauth e sessão Django. Identificar a conta por identidade Google validada, usando e-mail verificado na autorização inicial; não confiar em e-mail enviado pelo frontend. Verificar bloqueio/allowlist em login e autorização nas requisições. Configurar contas por ambiente, sem publicar seus e-mails de acesso no código. O contato público do autor não define automaticamente a conta administrativa.

Sessão em cookie HttpOnly/Secure em produção, proteção CSRF nas mutações e login OAuth com state. Não guardar tokens de sessão em localStorage. Login da aplicação serve também para Admin/Swagger; somente a conta de Marco recebe autorização administrativa. A esposa não recebe `is_staff` nem acesso à documentação privada.

Todas as consultas e alterações passam pelo Django e são limitadas à biblioteca da qual o usuário é participante. Validar também relações recebidas: pessoa, exemplar, local e tag precisam pertencer à mesma biblioteca. Não expor tabelas do domínio pela Data API do Supabase; navegador não acessa PostgreSQL diretamente. Supabase será usado como banco, sem Supabase Auth nesta proposta.

## 5. Modelo de domínio proposto

| Entidade | Conteúdo principal e relações |
| --- | --- |
| Usuário | Identidade autenticada e autorização técnica separada da gestão da biblioteca. Modelo customizado Django desde o início. |
| Biblioteca | Nome e configuração; unidade de isolamento dos dados. |
| Participação | Usuário + biblioteca, único por par; todos com o mesmo poder de gestão nesta fase. |
| Livro/Edição | Biblioteca, título, autores, ISBNs opcionais, editora, edição, ano, idioma, capa e referências de origem. |
| Exemplar | Biblioteca, livro, número interno, localização opcional, aquisição, situação de acervo e motivo/data de baixa. |
| Local | Biblioteca, nome e pai opcional, formando árvore de profundidade variável. |
| Tag | Biblioteca, nome; várias tags por livro, sem hierarquia. |
| Pessoa | Biblioteca, nome e telefone obrigatórios, e-mail opcional; cadastro reutilizável. |
| Empréstimo | Biblioteca, exemplar, pessoa, data inicial, prevista, efetiva opcional e estado. |
| Compartilhamento | Biblioteca e digest do token ativo/revogável; não reutilizar identificadores previsíveis como credencial. |
| Importação/Linha | Sessão de importação, registro de origem, seleção, erro e resultado; suporte a retomada/idempotência. |

Datas de cadastro/atualização técnicas ficam separadas das datas de negócio. A capa e as tags pertencem à edição; exemplares idênticos compartilham esses dados. Sem entidade adicional de obra na primeira versão. Autores serão lista ordenada de nomes no cadastro bibliográfico, sem cadastro complexo de pessoas/autores.

Número interno: proposta de sequência imutável por biblioteca, atribuída com proteção de concorrência e unicidade no banco. Não implica impressão de etiquetas.

## 6. Catálogo e exemplares

Título e ao menos um autor são o mínimo do cadastro inicial. ISBN é opcional; livros sem autoria conhecida podem usar um nome editorial explícito a definir na interface, sem bloquear o cadastro por falta de dados externos. Demais campos bibliográficos são opcionais. Preservar valores de edição/ano fornecidos; não inventar metadados ausentes.

ISBNs válidos serão normalizados e comparados de forma equivalente entre ISBN-10 e ISBN-13 quando aplicável. Um ISBN não vazio não gera automaticamente duas edições na mesma biblioteca. Correspondência ambígua exige revisão. Mesmo título/autor sem ISBN apenas sugere possível duplicado, sem mesclar automaticamente.

Ao encontrar ISBN existente, mostrar edição e quantidade de exemplares e confirmar a criação de outra cópia. Edições e traduções diferentes ficam separadas. Correções manuais podem ser feitas antes/depois de salvar e não são sobrescritas por novas consultas externas.

Cada exemplar tem aquisição informável; se omitida, assume a data do cadastro. Usar aquisição no painel de últimas aquisições. Localização é opcional, com filtro de “sem localização” e atribuição/mudança em lote.

Proposta de filtros do catálogo: texto (título/autor/ISBN), tag, local incluindo descendentes e disponibilidade. Paginação, filtros e ordenação no servidor; visualização em capas/cards no celular e opção de tabela para gestão em telas maiores. Não carregar todo o acervo para filtrar no navegador.

Baixa por venda, doação ou perda preserva exemplar e empréstimos. Excluir definitivamente apenas cadastros equivocados sem histórico/dependências; confirmar na interface. Exemplar baixado não conta como disponível nem aparece como parte do acervo ativo compartilhado. Reativação com confirmação é proposta para corrigir baixas equivocadas.

## 7. Locais

Hierarquia livre, por exemplo:

- Trabalho → Estante 1 / Estante 2 / Mesa.
- Casa → Escritório → Estante → Prateleira 1.
- Casa → Sala.

Nomes são cadastráveis, não uma estrutura fixa. Mover ou renomear um local preserva os vínculos. Impedir ciclos e pais de outra biblioteca. Proposta: não excluir local com exemplares ou sublocais; primeiro mover os vínculos. Mudanças em lote devem apresentar quantidade e destino para confirmação.

O empréstimo não substitui a localização pelo nome da pessoa. Preservar o lugar de origem para guardar o livro quando retornar. Não incluir histórico de mudanças físicas nesta versão.

## 8. Empréstimos

Pessoa reutilizável com nome/telefone obrigatórios e e-mail opcional, sem exigir unicidade de nome ou telefone. Permitir corrigir contatos; histórico permanece associado à pessoa. Proposta: impedir exclusão de pessoa com empréstimos, oferecendo arquivamento após encerrar pendências.

Três datas: empréstimo, devolução prevista e devolução efetiva. Padrão proposto: empréstimo hoje e previsão de um mês calendário, ajustando ao último dia do mês quando necessário (31/01 → 28/02 ou 29/02). Ambas editáveis para registrar empréstimos anteriores; efetiva não anterior ao início e prevista não anterior ao início. Não criar histórico de prorrogações.

Estados propostos: aberto, devolvido, encerrado por perda. Apenas um empréstimo aberto por exemplar, protegido no banco e em transação, inclusive contra ações simultâneas. Novo empréstimo exige exemplar ativo. Devolução preenche data efetiva; perda encerra sem preencher devolução fictícia e dá baixa no exemplar. Venda/doação com empréstimo aberto é bloqueada até regularizar a devolução; perda tem fluxo próprio.

Atraso calculado: estado aberto e previsão anterior à data de hoje em America/Sao_Paulo. Vencimento hoje não é atraso. Mostrar destaque textual e visual, sem depender apenas de cor. Sem e-mails de cobrança.

Histórico consultável por pessoa e exemplar, incluindo devolvidos e perdas. Não oferecer exclusão destrutiva desse histórico pelo frontend. Disponibilidade: livro tem ao menos um exemplar ativo sem empréstimo aberto.

## 9. Busca externa, câmera e imagens

**Proposta técnica:** adaptadores de provedores, Google Books como primeira fonte e Open Library como alternativa. Busca no backend com timeout, limites, tratamento de quota e metadados de proveniência. Não depender dessas APIs para consultar livros já salvos. Validar requisitos de atribuição, cache e uso de imagens de cada provedor antes de integrar; não presumir autorização de copiar capas externas para Cloudinary.

Câmera: ler códigos de livro/ISBN compatíveis, validar antes de consultar, permitir digitação manual e tratar permissão negada. Selecionar biblioteca de leitura mantida na implementação, sem depender exclusivamente da API BarcodeDetector. Fluxo contínuo: ler → revisar → confirmar → próximo, mantendo local escolhido e impedindo múltiplas submissões do mesmo scan. Persistir somente após confirmação.

Cloudinary para capas enviadas manualmente. Proposta inicial: JPEG/PNG/WebP, até 5 MB; processar dimensões e compressão para capas, rejeitar formatos inesperados, remover metadados desnecessários. Upload direto com autorização assinada pelo backend, sem segredo Cloudinary no cliente e sem passar a imagem inteira por Functions. Cada upload deve ser associado e autorizado pela biblioteca. IDs de mídia ficam no banco.

Capas externas podem permanecer como URL da fonte quando seus termos assim determinarem; indisponibilidade mostra placeholder e permite envio manual. Não incluir fotos adicionais por exemplar nesta versão. Exclusão de arquivo compartilhado só quando não houver referências; limpeza de uploads abandonados com limites para não consumir créditos excessivamente.

## 10. Importação Goodreads

CSV exportado pelo próprio usuário, sem scraping da conta nem importação de histórico de leitura/avaliações. Fluxo: enviar → validar → visualizar registros → selecionar livros possuídos → revisar correspondências → confirmar → acompanhar resultados.

Criar um exemplar por livro selecionado; quantidade adicional ajustada depois. Livros existentes são ignorados por padrão, com ação explícita para adicionar cópia. ISBN correspondente tem prioridade; ID Goodreads persistido auxilia reimportações. Sem mesclar ambiguidades por título/autor.

**Proposta técnica:** limite inicial de 5.000 linhas/3 MB, mensagens explicativas para excesso e arquivos inválidos. Não guardar o CSV original indefinidamente: manter sessão/linhas por até sete dias para retomada e depois limpar. Nunca registrar seu conteúdo em logs.

Processar lotes pequenos em requisições limitadas (ponto de partida: 25 linhas por lote), idempotentes por importação/linha/ação e com transação por linha. Exibir criados, ignorados e erros; repetir um lote não duplica exemplares. Persistir o progresso no servidor e permitir retomar após fechar o navegador. Evitar consultas externas em massa durante o salvamento; metadados faltantes não impedem importação e podem ser completados depois. Sem worker permanente ou fila adicional nesta versão.

## 11. Catálogo compartilhado

Link com token aleatório forte, sem login, somente leitura. Um link ativo por biblioteca; desativar/renovar invalida imediatamente o anterior. Não listar bibliotecas publicamente, não incluir em sitemap e orientar não indexação. Isso não impede repasse do link.

Resposta pública usa schemas próprios contendo apenas dados bibliográficos, capa, tags e disponibilidade agregada. Sem contatos, localizações, histórico, números internos ou ferramentas de gestão. Não expor dados privados sequer em HTML inicial, JSON ou mensagens de erro.

Proposta: não cachear respostas autenticadas nem páginas/APIs por token nesta fase, para simplificar revogação. Não enviar token a analytics; política de referrer restritiva e cuidado com URLs nos logs. Capas públicas não são mídia confidencial; uploads não autorizam publicar arquivos arbitrários.

## 12. Interface e identidade

Menu superior aprovado, áreas principais Painel, Livros, Empréstimos e Locais. Pessoas acessíveis no fluxo de empréstimos; importar dentro de Livros; compartilhamento e Sobre em ações secundárias. Avatar/menu de conta e alternância de tema no cabeçalho. Esses agrupamentos são proposta técnica/editorial para evitar sobrecarregar a barra.

Painel com totais de edições/exemplares ativos, empréstimos abertos, atrasos e últimas aquisições. Dados distintos com rótulos claros. Sem estatísticas de leitura.

Preservar tipografia e referências de acabamento de cinco-ministerios e dons, com a paleta inspirada na Siloé aprovada em 04/11/2026, integrada ao PrimeVue:

| Token | Claro | Escuro |
| --- | --- | --- |
| Primária / links | #053227 | #83c6a7 |
| Ação em âmbar | #ffbd59 | #ffbd59 |
| Dourado decorativo | #daaa60 | #daaa60 |
| Fundo | #fffaf4 | #0b1915 |
| Superfície | #ffffff | #142a23 |

Inter para corpo/títulos, espaçamento fluido e cantos arredondados. Ajustar contrastes por função sem usar dourado de baixo contraste como texto pequeno. Tema segue a preferência do sistema (`prefers-color-scheme`) e acompanha suas alterações enquanto não houver escolha manual. Sem preferência detectável ou sem suporte, usar escuro. Oferecer Claro, Escuro e Sistema; persistir a escolha no dispositivo. A escolha manual tem precedência até selecionar Sistema novamente. Cabeçalho em verde profundo #053227 e ações em âmbar com texto verde profundo nos dois temas; texto do tema escuro #fffaf4 e secundário #b9cbc1. Navegação por teclado, foco visível, labels, estados de erro/vazio/carregamento e confirmação de ações importantes.

Rodapé: **“Julib — Sua biblioteca, bem organizada”**, com Julib levando à homenagem à Juliana Mendes na página Sobre. Sem link separado de homenagem. Incluir GitHub, contato, apoio e autoria; versão do build como proposta.

Sobre: apresentação, funcionamento, privacidade real, tecnologias, autoria Marco André Mendes, licença MIT, contribuição, projetos relacionados (Dons e Cinco Ministérios) e apoio via PIX. Dados autorizados: GitHub `marrcandre`, LinkedIn `marrcandre`, contato/chave PIX `marcoandre@gmail.com`. QR Code e copiar PIX com retorno de sucesso/erro; doação voluntária, sem cobrar acesso.

PWA online: manifesto, ícones e apresentação instalável; aviso de falta de conexão sem fingir salvamento. Não cachear respostas privadas em service worker. Validar instalação, login Google e câmera em Chrome no Poco F5 e Samsung A34; desktop responsivo também integra o teste.

## 13. Estrutura técnica e deploy

Monorepositório proposto: backend/, frontend/, docs/, .github/workflows/. README, LICENSE MIT, CONTRIBUTING, .env.example sem segredos, .gitignore e documentação operacional. Ignorar .superpowers/, dumps, chaves, ambientes e uploads locais. Não publicar arquivos do acervo.

Frontend SPA Vue com Vite, TypeScript, PrimeVue e Vue Router. Estado global apenas quando necessário; cliente API tipado a partir do OpenAPI para reduzir divergência. Backend modular Django (contas/bibliotecas, catálogo, circulação, importação), services para operações de negócio usados tanto pela API quanto pelo Admin; schemas com campos explícitos para evitar exposição acidental. Transações e constraints no PostgreSQL. Não criar abstrações de microserviços.

Proposta de topologia: dois projetos Vercel no mesmo repositório, frontend e backend. O frontend encaminha /api, /accounts e /admin ao backend por rewrites, preservando uma origem pública para cookies e OAuth. Evitar depender de cookies entre subdomínios vercel.app distintos. Validar redirects, Set-Cookie, CSRF, URLs externas e Swagger pelo caminho público antes de aceitar o deploy. API versionada em /api/v1; documentação e schema protegidos em rotas próprias.

PostgreSQL Supabase acessado apenas pelo Django; usar pooler adequado para Functions, com configurações de prepared statements/cursors compatíveis. Migrações/backup usam endpoint compatível com essas operações, separado se necessário. Região do banco e backend próximas. Local e CI usam PostgreSQL separado, sem credenciais/dados reais. Execução Python síncrona inicialmente para simplificar transações; sem async indiscriminado.

Não considerar o filesystem de Functions como armazenamento persistente. Estáticos do deploy na CDN Vercel; mídia no Cloudinary. Nenhuma infraestrutura externa será criada até aprovação e configuração das contas.

## 14. TDD, CI/CD e Admin/Swagger

TDD nas regras de negócio e fluxos: teste relevante falha → implementação mínima → refatoração. Backend: pytest/pytest-django, PostgreSQL nos testes que verificam constraints/concorrência; Ruff e mypy com suporte Django. Frontend: Vitest/Vue Test Utils, vue-tsc e lint; Playwright para jornadas essenciais. Dependências/versões fixadas com uv.lock e lockfile frontend; ferramenta de pacotes frontend a decidir no plano.

Provas essenciais: isolamento entre bibliotecas; duas contas permitidas e outra recusada; esposa sem Admin/Swagger; CRUD e edição manual; duplicidade ISBN; concorrência no empréstimo; mês calendário; atraso; devolução/perda; locais/ciclos/lote; importação parcial/idempotência; link revogado e ausência de campos privados; upload; instalação online; tema e fluxos móveis. APIs externas simuladas na CI, sem depender de contas reais ou cotas para passar.

Admin registrado desde cada entidade nova, com busca/filtro e restrições de integridade. Ações relevantes passam pelos mesmos services; impedir edição bruta que burle empréstimos/baixas. Não prometer “funcional” apenas porque a página abre. Testar operações e autorização. Swagger deve gerar schema e executar chamadas com sessão/CSRF; somente Marco acessa documentação/schema em produção.

GitHub Actions roda checks em PRs e na principal. Deploy de produção executado apenas após sucesso dos checks no mesmo commit, sem deploy automático paralelo por push. Não disponibilizar segredos em PRs de forks. Proposta: desativar previews automáticos e auto deploy Git da Vercel, usando workflow de deploy dependente da CI.

Sequência proposta: verificar → build → checar migrações pendentes/revisão de impacto → backup pré-migração quando aplicável → migrações compatíveis → backend → frontend → smoke de saúde, schema e caminhos de login/documentação. Serializar deploys de produção. Falha interrompe promoção; não publicar frontend que dependa de backend não publicado. Rollback de código só se compatível com schema; migrações destrutivas exigem transição, nunca reversão automática do banco.

## 15. Backups e operação gratuita

**Confirmado:** banco diariamente, cópia criptografada e comprimida, retenção sete dias, chave de recuperação com o usuário e teste de restauração. Não se limita a CSV de livros: incluir pessoas, empréstimos, relações e esquema. Não incluir segredos do ambiente na cópia de dados.

**Decisão confirmada em 04/11/2026:** workflow operacional em repositório privado separado, apenas para backups, sem dividir backend/frontend. Guardar artifacts cifrados somente nesse repositório. GitHub Secrets para credenciais, chave pública para cifrar; chave privada de recuperação guardada fora do GitHub. Documentar como recuperar mesmo se perder acesso à aplicação. Não versionar dumps ou mídias em commits.

**Proposta de mídia:** no mesmo processo diário, copiar os arquivos Cloudinary referenciados pelo banco para um pacote cifrado, com manifesto de IDs e referências. Guardar sete snapshots completos apenas se a medição comprovar encaixe nas cotas de artifacts e tráfego; se exceder, adotar arquivos de mídia deduplicados com manifesto diário, conservando cada arquivo enquanto referenciado por qualquer um dos sete manifestos retidos. A rotação dos artifacts deve renovar a retenção dos arquivos ainda referenciados antes de expirar a cópia anterior. Essa alternativa precisa de teste de restauração e medição próprios. Se nem assim couber, registrar impedimento e solicitar escolha de outro destino privado gratuito antes de ativar o backup de mídia. Não reduzir silenciosamente a cobertura. URLs de capas externas não são cópias dos arquivos e não garantem recuperação da fonte.

Teste inicial e após mudanças no mecanismo: restaurar em PostgreSQL temporário e validar contagens, relações e amostras de arquivos; documentar recuperação da mídia e atualização de referências. Relatório de falha no GitHub Actions para Marco; configurar notificações da própria plataforma sem contratar serviço. Agendamento não é SLA e pode atrasar/falhar; documentar execução manual e conferência da última cópia. Perda possível desde a última execução bem-sucedida.

Cotas verificadas em documentação oficial nesta data: Supabase Free anuncia 500 MB de banco e pode pausar por baixa atividade em sete dias; Cloudinary mede armazenamento, transformações e entrega por créditos; GitHub Actions tem limites de uso/armazenamento para repositórios privados. Medir banco + sete cópias + mídia + CI antes de declarar capacidade gratuita. Não contratar add-ons nem ativar cobrança automática. Não usar backups como artifício para contornar regras de inatividade.

Vercel Hobby é destinado a uso pessoal/não comercial. Aplicação inicial é pessoal e a doação é voluntária; antes de futura abertura/monetização, revisar elegibilidade e termos do plano. Sem garantia de uptime dos planos gratuitos. Fornecer checklist operacional curto com cotas, última cópia, pausa/restauração e logs sem dados pessoais.

## 16. Escolhas propostas e decisões ainda necessárias

As seguintes escolhas são do assistente e podem ser aprovadas ou corrigidas na revisão: sessão Django/allauth, Google também no Admin, topologia de mesma origem, mês calendário, modelos/services, limites de importação/upload, Google Books com alternativa Open Library, PWA online e organização de telas.

**Decisão confirmada em 04/11/2026:** usar um repositório privado operacional para os backups, mantendo o código em um único repositório público. O aceite desta decisão não equivale à aprovação integral deste desenho nem à criação dos repositórios.

A capacidade da cópia de mídia depende de medição; a implementação não pode alegar backup completo antes de comprovar destino e restauração. Cotas e políticas serão verificadas novamente na configuração, sem alterar o orçamento autorizado.

Detalhes delegados ao implementador: versões compatíveis, gerenciador frontend, scanner mantido, nomes de módulos/rotas secundárias, índices, limites de timeout/lote ajustados por medição, detalhes dos formulários e testes. Não podem ampliar o escopo ou ativar serviços pagos.

## 17. Fontes e referências

Documentação consultada em 03/11/2026; limites podem mudar.

- [Django na Vercel](https://vercel.com/docs/frameworks/full-stack/django) e [limites de Functions](https://vercel.com/docs/functions/limitations).
- [Monorepositórios Vercel](https://vercel.com/docs/monorepos), [Storage](https://vercel.com/docs/storage) e [Hobby](https://vercel.com/docs/plans/hobby).
- [Supabase conexões](https://supabase.com/docs/guides/database/connecting-to-postgres), [preços](https://supabase.com/pricing), [pausa](https://supabase.com/docs/guides/platform/free-project-pausing) e [backup Actions](https://supabase.com/docs/guides/deployment/ci/backups).
- [Cloudinary uploads](https://cloudinary.com/documentation/upload_images) e [planos](https://cloudinary.com/documentation/billing_and_plans).
- [GitHub Actions uso](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- [Django Ninja](https://django-ninja.dev/quickstart/), [autenticação](https://django-ninja.dev/guide/authentication/), [CSRF](https://django-ninja.dev/guide/csrf/) e [allauth](https://docs.allauth.org/en/latest/socialaccount/configuration.html).
- [Open Library APIs](https://openlibrary.org/developers/api) e [capas](https://openlibrary.org/dev/docs/api/covers). Google Books é proposta de provedor; termos de uso de imagens ainda serão verificados na integração.
- [Goodreads exportação](https://help.goodreads.com/s/question/0D51H00005UUXHhSAP/exportation-of-the-library).
- [PWA instalável](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).
- Referências locais: cinco-ministerios/src/styles/tokens/, cinco-ministerios/src/views/AboutView.vue, cinco-ministerios/src/components/ui/AppHeader.vue e AppFooter.vue; dons/packages/frontend/src/styles/tokens.css, views/AboutView.vue, components/AppHeader.vue e components/ui/AppFooter.vue.
- Protótipo aprovado: navegação superior em .superpowers/brainstorm/64698-1793735547/content/navigation-footer-v3.html (artefato local de discussão, não código do produto).

## 18. Revisão do desenho

Revisão independente concluída em 03/11/2026. O revisor apontou duas questões: aceite do repositório operacional privado e alternativa caso as cópias completas de mídia excedam a cota. A primeira foi aceita pelo usuário em 04/11/2026; a segunda recebeu uma estratégia técnica de deduplicação, sujeita à medição e teste de restauração. Não foram apontadas outras lacunas relevantes para planejar a implementação.

O diretório ainda não é um repositório Git; este documento está salvo localmente, sem commit ou publicação. A criação/configuração do repositório integra o trabalho posterior à aprovação.

### Atualização em 04/11/2026

Usuário confirmou o repositório privado operacional para backups. Após leitura e alterações locais, o usuário autorizou consolidar e seguir para implementação em 04/11/2026.

## 19. Paleta aprovada em 04/11/2026

### Referência adicional de cores — 04/11/2026

- Usuário solicitou analisar https://comunidadesiloe.com.br/ como possível referência de paleta.
- Inspeção do HTML e da página renderizada encontrou verde profundo #053227, verde #074e3d, âmbar #ffbd59 (também #ffbe5a), dourado #daaa60, creme #fffaf4 e branco #ffffff. Esses valores são cores presentes no site, não uma especificação oficial de design tokens.
- Proposta: usar verde profundo como primária e âmbar como destaque, creme no fundo claro e superfícies brancas; manter Inter e navegação já escolhidas.
- Tema escuro precisará ser derivado para o Julib; não foi identificado um seletor de tema claro/escuro no site analisado. Garantir contraste por função, especialmente com âmbar.
- A nova paleta foi aprovada pelo usuário e substitui os valores de cores anteriores. Referência final de protótipo: .superpowers/brainstorm/79723-1793813939/content/siloe-palette-v2.html.

### Preferência de tema — decisão em 04/11/2026

Adotar a paleta da prévia Siloé. Seguir o tema do sistema quando detectável; escuro como fallback. Manter escolha manual. A aprovação visual foi posteriormente incorporada à autorização de implementação de 04/11/2026.

## 20. Consolidação para implementação — 04/11/2026

O usuário revisou o documento, acrescentou explicitamente filtros por tags e links para Dons/Cinco Ministérios e autorizou avançar para implementação. Propostas técnicas deste desenho passam a orientar a execução, com limites de cotas e integrações externas ainda sujeitos à verificação real. A referência visual definitiva é a prévia Siloé. Busca por tags refere-se ao catálogo próprio; não pressupõe que a API externa conheça as tags da biblioteca.
