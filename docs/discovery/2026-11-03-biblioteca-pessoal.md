# Biblioteca pessoal — levantamento de requisitos e decisões

Documento em construção. Registra as informações fornecidas e as decisões tomadas durante a conversa. Não representa um projeto aprovado para implementação.

## Objetivo informado

Desenvolver uma aplicação web para registrar e gerenciar os livros da biblioteca pessoal.

## Preferências e requisitos informados

- Backend: Python com Django e Django REST Framework (DRF), usando uv.
- Banco de dados: PostgreSQL.
- Frontend: Vue.js.
- Interface responsiva, com CSS limpo e fluido.
- Hospedagem desejada: Vercel; distribuição dos componentes e viabilidade a validar na etapa de arquitetura.
- Desenvolvimento com TDD e CI/CD.
- Busca de livros por API externa, como Google Books ou alternativa, incluindo capas e demais informações.
- Registro da localização física dos livros, considerando vários locais, estantes e prateleiras.
- Controle de empréstimos.
- Controle de leituras foi mencionado inicialmente e depois retirado do escopo atual.
- Levantar e registrar requisitos, arquitetura e decisões técnicas antes de desenvolver.

## Pendências históricas na abertura do levantamento

A lista abaixo registra o início da conversa; muitas decisões foram resolvidas nas respostas subsequentes. Para o estado consolidado, consultar [requisitos e arquitetura](../superpowers/specs/2026-11-03-julib-design.md).

- Detalhes das contas de usuário, convites e permissões dos participantes.
- Escopo da primeira versão e critérios de sucesso.
- Necessidade de distinguir obras e edições além da separação já identificada entre dados do livro e exemplares físicos.
- Campos do catálogo, busca externa e cadastro manual.
- Estrutura e regras das localizações.
- Fluxos e regras de empréstimos.
- Autenticação, privacidade e permissões.
- Arquitetura de deploy, banco, armazenamento de capas e custos.
- Estratégia de testes, integração e entrega contínuas.
- Design, acessibilidade, importação, exportação e backups.

## Histórico da conversa

### 2026-11-03 — abertura

Registradas as ideias iniciais. Primeira questão a esclarecer: quem usará a aplicação e se cada pessoa terá uma biblioteca própria ou compartilhada.

### Público e compartilhamento — resposta do usuário

- No início, o usuário e sua esposa usarão a mesma biblioteca, com dados compartilhados.
- Futuramente, a aplicação poderá ser aberta a outras pessoas.
- O modelo futuro desejado permite que uma conta convide outras pessoas para participar de sua biblioteca pessoal.
- A definição de contas individuais, papéis e permissões ainda está em aberto.

### Proposta técnica a discutir

- Tratar biblioteca como uma entidade própria, associada a seus participantes, para acomodar o compartilhamento e a futura abertura a outros grupos.
- Proposta anterior de separar dados de leitura por pessoa não será desenvolvida nesta versão, pois o controle de leituras foi retirado do escopo.

### Escopo atual — decisão do usuário

- Manter apenas cadastro e consulta dos livros, localização física e controle de empréstimos.
- Deixar histórico de leitura e avaliações fora por enquanto; controle de progresso de leitura também não integra o escopo atual, limitado aos três itens acima.
- Contas individuais e permissões ainda não foram confirmadas; a resposta restringiu o escopo funcional.

### Livros duplicados — resposta do usuário

- O acervo contém cópias exatas do mesmo livro.
- O cadastro deve permitir múltiplos exemplares físicos de um mesmo livro.

### Proposta de modelagem decorrente

- Compartilhar os dados bibliográficos (título, autores, ISBN, editora, capa etc.) entre cópias da mesma edição.
- Representar cada exemplar físico separadamente, com localização e empréstimos próprios.
- Identificação dos exemplares na interface ainda precisa ser definida.

### Localizações físicas — resposta do usuário

Organização atual:

- Trabalho: duas estantes e uma mesa.
- Casa: escritório e sala.
- Escritório de casa: uma estante com prateleiras; é necessário localizar os livros por prateleira.
- A subdivisão dos livros da sala e das estantes do trabalho ainda não foi informada.

### Proposta para localizações — a confirmar

- Permitir uma hierarquia flexível de locais, sem exigir a mesma quantidade de níveis para todos os exemplares.
- Exemplos: Trabalho > Mesa; Trabalho > Estante 1; Casa > Escritório > Estante > Prateleira 1.
- Os nomes apresentados são exemplos; nomes e numeração definitivos serão cadastrados pelo usuário.
- Cada exemplar aponta para sua localização específica.
- No empréstimo, manter a localização de origem do exemplar para orientar sua devolução; regra ainda a confirmar.

### Empréstimos — campos iniciais informados pelo usuário

- Nome da pessoa que recebeu o exemplar.
- Telefone.
- E-mail.
- Data do empréstimo.
- Obrigatoriedade definida posteriormente: nome e telefone obrigatórios; e-mail opcional.
- Prazo previsto, registro da devolução e reutilização do cadastro de pessoas ainda precisam ser definidos.

### Acompanhamento dos empréstimos — resposta do usuário

- É necessário controlar quais livros estão emprestados e a data de devolução.
- Esclarecido na resposta seguinte: registrar tanto a data prevista quanto a data efetiva de devolução.

### Datas e prazo dos empréstimos — decisão do usuário

- Registrar a data prevista de devolução e a data efetiva de devolução.
- Usar um mês de empréstimo como prazo padrão.
- Proposta a confirmar no desenho: preencher a previsão automaticamente e permitir alterá-la em cada empréstimo.
- Regra exata de cálculo de um mês (mês calendário ou quantidade fixa de dias) ainda não definida.
- Obrigatoriedade dos campos de contato definida na resposta seguinte.

### Contatos de quem recebe empréstimos — decisão do usuário

- Nome obrigatório.
- Telefone obrigatório.
- E-mail opcional.
- Ainda em aberto: manter um cadastro reutilizável de pessoas ou registrar os contatos em cada empréstimo.

### Histórico de empréstimos — decisão do usuário

- Permitir consultar o histórico de empréstimos de cada pessoa.
- Permitir consultar o histórico de empréstimos de cada exemplar.
- Preservar os registros de empréstimo após a devolução.
- Cadastro reutilizável de pessoas, compartilhado pela biblioteca, foi proposto; sua organização será consolidada no desenho.

### Busca e entrada de livros — decisão do usuário

- Buscar livros por título, autor e ISBN.
- Incluir leitura do código de barras pela câmera do celular para consultar o livro.
- Provedor externo e solução técnica para leitura de código ainda serão avaliados.
- Fluxo para livros não encontrados, cadastro manual e edição dos dados importados ainda precisam ser definidos.

### Organização temática — requisito do usuário

- Permitir cadastrar tags ou categorias para organizar os livros.
- Decisão posterior: usar tags livres nesta versão, sem hierarquia de categorias.
- Proposta de funcionamento: tags compartilhadas pela biblioteca, com múltiplas tags por livro e filtro do catálogo por tag; detalhes serão consolidados no desenho.

### Classificação — decisão do usuário

- Tags livres atendem à versão atual.
- Categorias e subcategorias ficam fora do escopo atual.

### Acesso e permissões — decisão do usuário

- Cada participante terá seu próprio login.
- Autenticação pela conta Google.
- Nesta versão, todos os participantes convidados para gerenciar a biblioteca terão permissão total para operar o acervo, locais e empréstimos.
- Não haverá diferenciação de papéis de gerenciamento nesta versão.
- Permissão para convidar/remover participantes, transferência de responsabilidade e exclusão da biblioteca ainda precisam ser esclarecidas; não presumir essas ações administrativas a partir da permissão sobre o acervo.
- A disponibilidade de convites já na primeira versão ou apenas posteriormente ainda precisa ser definida.

### Fases de acesso e compartilhamento — decisão do usuário

- Convites para gerenciar a biblioteca ficam para uma próxima fase.
- Na primeira versão, o acesso de gerenciamento será limitado às contas Google do usuário e da esposa, conforme proposta aceita na conversa.
- Incluir compartilhamento da coleção com amigos por link, em modo somente leitura.
- Ainda a definir: necessidade de login para visitantes, dados visíveis, forma de desativar/renovar o link e eventual indexação pública.
- Dados de contatos e histórico de empréstimos não têm exposição autorizada; sua visibilidade precisa ser tratada separadamente do catálogo compartilhado.

### Link de compartilhamento — decisão do usuário

- O catálogo compartilhado abre sem login para qualquer pessoa que tenha o link.
- Os gestores podem desativar o link ou gerar um novo, invalidando o anterior.
- Visibilidade proposta na conversa: capa, dados do livro, tags e disponibilidade para empréstimo; localizações físicas, nomes, contatos e histórico de empréstimos restritos aos gestores. Não houve confirmação específica desses campos; consolidar na revisão do desenho.
- Não foi solicitado fluxo de reserva ou solicitação de empréstimo pelo visitante.

### Volume e dados existentes — resposta do usuário

- Acervo estimado em cerca de 1.000 exemplares.
- Não existe uma relação atual dos livros possuídos.
- O usuário possui muitos livros marcados como lidos no Goodreads e tem interesse em avaliar exportação e importação.
- Livros lidos no Goodreads não devem ser presumidos como exemplares atualmente possuídos.
- Escopo e prioridade da importação ainda não definidos.

### Importação do Goodreads — decisão do usuário

- O usuário precisa selecionar durante a importação quais livros pertencem ao acervo físico.
- Não há uma marcação no Goodreads que possa ser usada como critério automático de posse.
- A importação deve oferecer seleção dos registros antes de criar os livros/exemplares.
- Proposta: usar arquivo CSV exportado pelo Goodreads, com prévia e revisão antes da confirmação.
- Fonte consultada sobre exportação CSV: https://help.goodreads.com/s/question/0D51H00005UUXHhSAP/exportation-of-the-library
- Decisão do usuário: incluir a importação do Goodreads já na primeira versão.

### Prioridade de importação — decisão do usuário

- A primeira versão inclui importação do Goodreads com seleção dos livros antes de salvar.

### Hospedagem — esclarecimento pendente

- Vercel é a hospedagem desejada informada inicialmente.
- Ainda esclarecer se é requisito para todos os componentes ou preferência para o frontend, permitindo backend e PostgreSQL em outros serviços.
- Nenhum provedor adicional foi escolhido ou avaliado tecnicamente até aqui.

### Infraestrutura e código — preferências atualizadas do usuário

- Hospedar backend Django e frontend na Vercel.
- Usar PostgreSQL do Supabase e Cloudinary para imagens, sujeitos à confirmação das capacidades dos serviços.
- Hospedar o código no GitHub.
- Preferência inicial por um repositório para backend e outro para frontend; decisão aberta à discussão.
- Vue.js continua como primeira opção; React pode ser considerado.

### Verificação de documentação oficial — 2026-11-03

- Vercel suporta Django e entrega arquivos estáticos pela CDN; portanto, CSS, JavaScript e imagens incluídas no deploy são suportados.
- Uploads persistentes de usuários precisam de armazenamento próprio para esse fim. Vercel Blob é uma opção da plataforma; Cloudinary é outra opção válida para imagens, não uma exigência da Vercel.
- Bancos PostgreSQL podem ser conectados à Vercel via provedores externos e integrações do Marketplace. Supabase é uma escolha válida, não o único provedor possível.
- Supabase recomenda pooler em modo transação para conexões serverless; compatibilidade e configurações do driver Django deverão ser consideradas.
- Hospedagem Django em Functions implica considerar limites de execução e tamanho de requisições no desenho da importação e dos uploads.
- Proposta do assistente, ainda não escolhida: monorepositório com backend/, frontend/ e docs/, mantendo deploys separados. Alternativa: dois repositórios, com coordenação explícita de mudanças na API.
- Não houve escolha final entre Vue e React.

Fontes:

- https://vercel.com/docs/frameworks/full-stack/django
- https://vercel.com/docs/storage
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/monorepos
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://cloudinary.com/documentation/upload_images

### Organização do repositório — decisão do usuário

- Usar um único repositório no GitHub (monorepositório).
- Organização proposta: backend/, frontend/ e docs/.
- Motivo da recomendação apresentada: coordenar mudanças da API e interface no mesmo PR, mantendo documentação e validação juntas.
- Alternativa considerada: dois repositórios, com administração independente e maior necessidade de coordenar mudanças conjuntas.
- Deploys independentes para backend e frontend continuam como proposta técnica, a consolidar no desenho.
- Nenhum repositório remoto ou estrutura de aplicação foi criado nesta etapa de levantamento.

### Critérios para frontend — resposta do usuário

- Experiência baixa tanto em Vue quanto em React.
- Deseja intervir o mínimo possível no frontend.
- Prioriza facilidade de desenvolvimento pelo agente e uma biblioteca rica de componentes para uma aplicação funcional.

### Alternativas de frontend — recomendação pendente de escolha

- Vue + TypeScript + PrimeVue: recomendação do assistente, preservando a preferência inicial e oferecendo componentes prontos para tabelas, seleção, formulários e demais fluxos de gestão.
- React + TypeScript + PrimeReact: alternativa com biblioteca ampla, sem vantagem específica identificada para os requisitos desta aplicação.
- A facilidade para agentes é um julgamento de engenharia, não uma garantia de superioridade de um framework. Convenções, componentes consistentes e testes serão critérios de manutenção.
- Proposta: usar tema pronto da biblioteca e CSS próprio para layout e adaptações responsivas.
- Fontes consultadas: https://primevue.dev/datatable/ e https://primereact.dev/components
- Nenhuma escolha final de framework ou biblioteca de componentes foi confirmada nesta resposta.

### Frontend e tipagem do backend — decisões do usuário

- Frontend confirmado: Vue + TypeScript + PrimeVue.
- Backend em Python com anotações de tipo.
- Django e uv permanecem nas preferências confirmadas; DRF está aberto a substituição após comparação.

### API Python — alternativas em avaliação

- Django Ninja: recomendação do assistente para schemas tipados com validação via Pydantic e geração de OpenAPI, preservando ORM, migrações e demais recursos do Django.
- Django REST Framework: alternativa com serializers, viewsets e políticas de autenticação/permissão; permite anotações, mas os contratos de entrada e saída seguem o modelo de serializers.
- FastAPI: alternativa baseada em tipos e Pydantic, porém substituir Django exigiria redefinir ORM, migrações e administração; não recomendado pelo assistente para este projeto.
- Proposta ainda não aprovada: Django + Django Ninja, uv e verificação estática de tipos na CI. Ferramenta e rigor da checagem serão definidos posteriormente.
- Anotações Python não substituem validação de entrada nem regras de autorização por biblioteca.

Fontes oficiais consultadas:

- https://django-ninja.dev/quickstart/
- https://www.django-rest-framework.org/api-guide/viewsets/
- https://www.django-rest-framework.org/api-guide/authentication/
- https://fastapi.tiangolo.com/features/

### Framework da API e ferramentas administrativas — decisão do usuário

- Adotar Django Ninja para a API, mantendo Django e uv.
- Manter Django Admin funcional durante toda a evolução do projeto.
- Manter Swagger/documentação interativa da API funcional durante toda a evolução do projeto.
- Esses recursos são requisitos contínuos, não apenas ferramentas temporárias de desenvolvimento.

### Propostas para garantir esses requisitos — a consolidar

- Registrar no Admin as entidades gerenciáveis, com filtros, buscas e validações compatíveis com as regras da aplicação.
- Fazer Admin e API respeitarem as mesmas invariantes de negócio, incluindo empréstimos e integridade dos exemplares.
- Validar na CI a geração do OpenAPI, a disponibilidade da documentação e os fluxos administrativos relevantes.
- Swagger deve permitir autenticar e executar chamadas autorizadas, não apenas exibir os endpoints.
- Ainda a definir: acesso ao Admin/Swagger em produção e autenticação para esses recursos. Login Google no aplicativo não implica automaticamente acesso ao Admin.

### Acesso ao Admin e Swagger — decisão do usuário

- Em produção, somente o usuário precisa acessar Django Admin e Swagger.
- A esposa mantém permissão total de gestão pela aplicação, sem necessidade de acesso a essas ferramentas.
- Separar a autorização das ferramentas técnicas da participação na biblioteca.
- Método de autenticação dessas ferramentas ainda em aberto; a resposta definiu quem acessa, sem confirmar uso do Google ou de credenciais administrativas próprias.

### Orçamento de infraestrutura — decisão do usuário

- Usar apenas planos gratuitos na primeira versão.
- Seleção e configuração de hospedagem, banco, mídia e CI/CD devem respeitar essa restrição.
- Não ativar recursos pagos ou upgrades automaticamente.
- Cotas atuais, política de inatividade, backups e limitações de cada plano precisam ser verificadas antes de consolidar a arquitetura.
- Método de backup/exportação e separação dos ambientes ainda estão em aberto.

### CI/CD — decisão do usuário

- Publicar automaticamente alterações aprovadas e integradas à branch principal, desde que todos os testes e verificações passem.
- O deploy de produção deve depender do resultado da CI; apenas conectar o deploy ao push sem essa garantia não atende ao requisito.
- TDD permanece requisito de desenvolvimento.
- Ainda definir verificações por componente, testes integrados, tratamento de migrações e rollback.

### Próxima definição — ambientes de validação

- Ainda decidir entre validação local/CI seguida de produção ou também disponibilizar ambiente online de homologação com dados separados.
- Qualquer ambiente adicional precisa caber nos planos gratuitos.

### Ambientes — decisão do usuário

- Começar com validação local e na CI, seguida de deploy em produção.
- Não incluir ambiente online de homologação na primeira versão.
- Desenvolvimento e testes devem usar dados e banco separados dos dados reais de produção.
- Deploy automático permanece condicionado às verificações aprovadas.

### Backups automáticos — proposta explicada, ainda não aprovada

- Executar workflow agendado do GitHub Actions para exportar estrutura e dados do PostgreSQL usando ferramenta compatível (CLI Supabase/pg_dump).
- Comprimir e criptografar a cópia, usando credenciais armazenadas em GitHub Secrets; guardar a chave privada de recuperação fora do repositório.
- Possível destino inicial: artifacts do Actions com retenção limitada, sem versionar dados pessoais no Git.
- Sugestão inicial: execução diária, retenção de sete dias, sujeita à verificação do tamanho real e das cotas gratuitas compartilhadas com a CI.
- Testar restauração em banco temporário/local antes de considerar o processo confiável. Recuperação de produção será deliberada, não automática.
- Dump do PostgreSQL inclui dados e referências de imagens, não os arquivos do Cloudinary. Estratégia para cópia das imagens ainda pendente.
- O usuário pediu explicação do funcionamento; frequência, retenção e destino ainda não escolhidos.
- Fontes: https://supabase.com/docs/guides/platform/backups ; https://supabase.com/docs/guides/deployment/ci/backups ; https://docs.github.com/en/billing/concepts/product-billing/github-actions

### Backup do banco — decisão do usuário

- Aprovada a proposta de backup automático diário do PostgreSQL, com retenção de sete dias.
- Usar GitHub Actions para gerar, comprimir e criptografar as cópias e armazená-las como artifacts com retenção limitada.
- Credenciais via GitHub Secrets e chave de recuperação também guardada pelo usuário fora do repositório.
- Verificar consumo das cotas gratuitas e testar restauração em banco temporário/local.
- Recuperação pode perder alterações posteriores à última cópia bem-sucedida.
- Backup dos arquivos de imagens continua pendente e não está incluído implicitamente no dump do banco.

### Capas enviadas pelos gestores — decisão do usuário

- Permitir enviar foto ou imagem de capa manualmente, além das capas obtidas por busca externa.
- O envio permite suprir capas ausentes ou substituir capas incorretas.
- Armazenamento de mídia proposto: Cloudinary, dentro do plano gratuito.
- Limites, formatos, processamento e backup dos arquivos ainda serão definidos no desenho.
- Ainda não foi decidido se imagens serão associadas ao cadastro bibliográfico compartilhado ou a exemplares individuais; não presumir suporte a fotos adicionais por exemplar.

### Saída de exemplares do acervo — decisão do usuário

- Permitir marcar exemplares como fora do acervo por venda, doação ou perda.
- Registrar o motivo da saída.
- Preservar o registro do exemplar e seu histórico de empréstimos após a saída.
- Regras para baixa de exemplar com empréstimo aberto, eventual reativação e visibilidade no catálogo compartilhado ainda precisam ser consolidadas.

### Cadastro gradual e localização em lote — decisão do usuário

- Permitir cadastrar exemplares sem localização definida.
- Permitir atribuir ou alterar a localização posteriormente.
- Permitir selecionar vários exemplares e atribuir a mesma localização em lote, incluindo uma prateleira específica.
- Esse fluxo deve apoiar o cadastro gradual do acervo estimado de 1.000 exemplares e os registros vindos da importação.

### Cadastro contínuo pelo celular — decisão do usuário

- Incluir na primeira versão um modo de cadastro contínuo por leitura de código de barras.
- Fluxo: ler código, revisar resultado, salvar exemplar e seguir para o próximo.
- Manter a localização escolhida entre os cadastros, até que o gestor a altere; localização continua opcional.
- Detecção de livro já cadastrado e confirmação de novo exemplar ainda precisam ser definidas.

### Duplicação no cadastro por ISBN — decisão do usuário

- Quando o ISBN já existir na biblioteca, mostrar o livro e a quantidade de exemplares cadastrados.
- Pedir confirmação antes de criar outro exemplar, evitando duplicação acidental sem impedir cópias legítimas.
- Regra de detecção para livros sem ISBN ainda pendente.

### Livros sem ISBN — decisão do usuário

- O acervo inclui livros sem ISBN.
- Permitir cadastro manual mesmo quando só título e autor estiverem disponíveis.
- ISBN e demais dados bibliográficos não podem ser exigidos para esse fluxo.
- Não presumir duplicidade apenas por título e autor; regra de sugestão de possíveis duplicados ainda será consolidada.

### Privacidade do catálogo compartilhado — decisão do usuário

- Confirmada a exposição somente de capa, dados do livro, tags e disponibilidade no link para amigos.
- Localização física, pessoas/contatos e histórico de empréstimos permanecem privados, acessíveis apenas aos gestores autorizados.
- Aplicar essa restrição também às respostas da API pública, não apenas aos elementos visíveis da interface.

### Datas do empréstimo — simplificação confirmada pelo usuário

- Manter somente data do empréstimo, data de devolução prevista e data de devolução efetiva.
- Não incluir histórico de alterações de prazo nem registros de prorrogação nesta versão.
- Essa decisão não altera a preservação do histórico dos empréstimos por pessoa e por exemplar.

### Empréstimos atrasados — decisão do usuário

- Na primeira versão, destacar visualmente os empréstimos atrasados na lista.
- Não incluir notificações por e-mail para atrasos nesta versão.
- Proposta de regra: considerar atrasado o empréstimo sem devolução efetiva cuja data prevista seja anterior à data atual; consolidar no desenho.

### Tela inicial — decisão do usuário

- Abrir a aplicação em um painel.
- Mostrar resumo dos livros/acervo, empréstimos e últimas aquisições.
- Ainda definir o significado de últimas aquisições: data real de aquisição ou ordem de cadastro. Essa distinção importa durante o cadastro inicial e a importação de livros antigos.

### Data de aquisição — decisão do usuário

- Registrar a data de aquisição por exemplar.
- Permitir informar a data real de compra, inclusive para livros antigos.
- Quando não informada, assumir a data do cadastro como data de aquisição.
- Usar a data de aquisição para ordenar as últimas aquisições do painel.
- Manter a data de cadastro separada como informação técnica; não substituir sua finalidade pela data de aquisição.

### Dados de compra — decisão do usuário

- Preço e local da compra ficam fora da primeira versão.
- Manter somente a data de aquisição conforme regra já definida.

### Elegibilidade para empréstimo — decisão do usuário

- Não incluir marcação de exemplar como “não emprestável” nesta versão.
- Proposta para disponibilidade: exemplar ativo no acervo e sem empréstimo em aberto; livro disponível quando houver ao menos um exemplar nessas condições.

### Quantidade inicial na importação — decisão do usuário

- Criar um exemplar para cada livro selecionado na importação do Goodreads.
- Permitir ajustar/adicionar cópias duplicadas posteriormente.
- Essa regra não autoriza duplicar registros automaticamente ao reenviar o mesmo arquivo; tratamento de reimportação será definido no desenho.

### Identificação dos exemplares — decisão do usuário

- Gerar automaticamente um número interno por exemplar, visível na aplicação.
- Usar essa identificação para distinguir cópias idênticas em empréstimos e mudanças de localização.
- Não exigir etiquetas físicas.
- Escopo da numeração e formato serão definidos tecnicamente no desenho.

### Localização durante empréstimos — decisão do usuário

- Preservar a localização de origem do exemplar enquanto ele estiver emprestado.
- Usar essa informação para orientar onde guardar o livro após a devolução.
- A situação de empréstimo é separada da localização cadastrada; não substituir estante/prateleira pelo nome da pessoa.

### Conectividade e PWA — resposta do usuário

- A aplicação pode funcionar somente com conexão à internet.
- O usuário demonstrou interesse em um PWA.
- Proposta a confirmar: incluir PWA instalável na primeira versão, com ícone e abertura em janela própria, mantendo os dados e operações dependentes da conexão.
- Não incluir sincronização offline nem fila de operações nesta versão.
- Comportamento de instalação depende do navegador e sistema; validar nos dispositivos utilizados.

### Dispositivos de uso — resposta do usuário

- Usuário: Poco F5.
- Esposa: Samsung A34.
- Priorizar esses aparelhos na validação de instalação do PWA, layout responsivo e leitura de códigos pela câmera.
- Navegadores usados ainda não informados.
- PWA instalável foi proposto para a primeira versão; interesse manifestado pelo usuário, com aprovação explícita do escopo ainda a consolidar na revisão.

### Navegador móvel — decisão do usuário

- Chrome nos dois aparelhos (Poco F5 e Samsung A34).
- Priorizar Chrome nesses dispositivos para validar interface responsiva, instalação do PWA e leitura de códigos pela câmera.

### Livros existentes na importação — decisão do usuário

- Se um livro selecionado do Goodreads já existir na biblioteca, ignorá-lo por padrão.
- Permitir que o gestor escolha explicitamente adicionar outro exemplar.
- Aplicar também em reimportações para evitar duplicação acidental.
- Critérios técnicos para identificar correspondências e tratar casos ambíguos serão definidos no desenho; não mesclar automaticamente apenas por título e autor.

### Edições e exemplares — decisão do usuário

- Manter um cadastro de livro por edição dentro da biblioteca.
- Exemplares idênticos compartilham os dados bibliográficos desse cadastro.
- Cadastrar edições ou traduções diferentes separadamente.
- Não é necessário presumir uma entidade adicional de obra para agrupar edições nesta versão.

### Liberação inicial de contas — decisão do usuário

- Cadastrar previamente os dois e-mails Google autorizados, do usuário e da esposa.
- Somente essas contas poderão acessar a gestão na primeira versão.
- Recusar outras contas Google até a implementação futura de convites.
- Não é necessário coletar os endereços nesta etapa; serão configurados na preparação do ambiente.

### Descoberta do catálogo compartilhado — decisão do usuário

- Manter a coleção não listada nesta fase, sem divulgação em buscadores.
- Preservar a decisão anterior de acesso sem login por link compartilhável, revogável e renovável.
- Incluir orientação de não indexação nas páginas compartilhadas.
- Não indexação não é controle de acesso: quem receber o link poderá abrir e repassá-lo, conforme explicado na conversa.

### Edição dos dados bibliográficos — decisão do usuário

- Permitir corrigir manualmente qualquer informação trazida pela API, antes e depois do cadastro.
- Novas consultas não devem sobrescrever automaticamente alterações feitas pelos gestores.
- Atualizações externas que alterem dados já salvos precisam de revisão/confirmação explícita.

### Gestão da hierarquia de locais — decisão do usuário

- Permitir criar, renomear e reorganizar livremente a hierarquia de locais.
- Manter os exemplares associados ao local ao renomear ou mover esse local na hierarquia.
- Permitir diferentes profundidades de hierarquia conforme a organização física da biblioteca.
- Regras de integridade (como impedir ciclos e tratar exclusão de locais ocupados) serão especificadas no desenho.

### Perda de exemplar emprestado — decisão do usuário

- Permitir registrar a perda de exemplar que esteja emprestado e encerrar o empréstimo por perda.
- Não preencher uma data de devolução efetiva quando a devolução não aconteceu.
- Preservar o histórico e distinguir encerramento por perda de empréstimo em aberto ou devolvido.
- Manter somente as três datas de empréstimo já definidas; não adicionar histórico de prorrogações.

### Identidade visual e tela Sobre — referências solicitadas pelo usuário

Referências locais examinadas em /home/marco/projetos/cinco-ministerios e /home/marco/projetos/dons.

- Reutilizar como referência os temas claro/escuro, tipografia e estilo da tela Sobre desses projetos.
- Ambos usam a mesma paleta principal: verde #1a4d2e e dourado #d4a843; fundo claro #f8f8f5 e superfície branca.
- Tema escuro: verde #2d8a5a, dourado #d4a82e, fundo #121212 e superfície #1e1e1e.
- Tipografia: Inter para títulos e corpo; cinco-ministerios também declara Roboto como fallback.
- Referências de acabamento: espaçamento em escala, cantos arredondados, bordas discretas e sombras leves; dons usa raios de 8 a 20 px.
- Incluir tela Sobre inspirada nas existentes, com apresentação do projeto, funcionamento, privacidade, autor/contatos, projetos relacionados e opção de doação.
- dons inclui contribuição via PIX com QR Code, chave copiável e feedback; cinco-ministerios inclui chave PIX copiável.
- Adaptar conteúdo de privacidade e tecnologias à biblioteca; não copiar afirmações de ausência de coleta de dados ou licença sem decisão própria.
- Integrar essa identidade ao tema do PrimeVue; não trocar a biblioteca por Vuetify apenas porque dons a utiliza.
- Dados de autor, links e destino da doação encontrados nas referências serão consolidados na revisão, sem presumir sua publicação neste projeto.

Arquivos de referência:

- /home/marco/projetos/cinco-ministerios/src/styles/tokens/colors.css
- /home/marco/projetos/cinco-ministerios/src/styles/tokens/typography.css
- /home/marco/projetos/cinco-ministerios/src/views/AboutView.vue
- /home/marco/projetos/dons/packages/frontend/src/styles/tokens.css
- /home/marco/projetos/dons/packages/frontend/src/views/AboutView.vue

### Autor, contatos e doação — autorização do usuário

- Reutilizar na tela Sobre os dados de autor, links de contato e chave PIX presentes nos projetos de referência.
- Autor: Marco André Mendes.
- GitHub: https://github.com/marrcandre
- LinkedIn: https://www.linkedin.com/in/marrcandre/
- E-mail de contato e chave PIX: marcoandre@gmail.com.
- Usar esses dados na apresentação e doação do projeto; não presumir que o e-mail seja também a conta de login autorizada sem configuração específica.
- QR Code e botão de copiar PIX seguem como proposta de apresentação inspirada em dons.

### Nome e história do projeto — decisão do usuário

- Nome oficial: Julib.
- O nome une Ju, apelido de Juliana (esposa do usuário), e lib, referência a biblioteca.
- Incluir a homenagem à Juliana na apresentação do projeto.
- Autor confirmado pelo usuário: Marco André Mendes.
- Alternativas discutidas: Estante da Ju e Nossa Estante; preferido Julib por ser curto, pessoal e adequado como nome de aplicação.
- Frase sugerida pelo assistente: “Sua biblioteca, bem organizada”; texto editorial a consolidar no desenho.

### Publicação do código e documentação — decisão do usuário

- Repositório público no GitHub, com licença MIT e README.
- Proposta para documentação: apresentação e funcionalidades, configuração local, variáveis de ambiente exemplificadas sem segredos, testes/TDD, arquitetura, deploy, backup/restauração e contribuição.
- Código público não altera a privacidade do acervo, contatos e empréstimos.
- Backups com dados pessoais não podem ser publicados como artifacts acessíveis no repositório público. A proposta anterior de artifacts no mesmo repositório precisa ser revista; destino privado a definir, preservando execução diária, criptografia e retenção de sete dias.

### Cabeçalho, rodapé e navegação — referências examinadas

- O usuário solicitou analisar cabeçalho e rodapé de cinco-ministerios e dons, mantendo em aberto menu lateral versus superior.
- cinco-ministerios: cabeçalho sticky com marca, navegação textual e alternância de tema; borda inferior discreta.
- dons: barra superior compacta com marca, ações, tema e avatar/menu da conta; acesso administrativo condicionado à autorização.
- Rodapés: marca/descrição, navegação, GitHub, contato, apoio ao projeto e autoria; dons também mostra versão.
- Proposta a avaliar visualmente: barra superior com marca, tema e conta; navegação principal superior no desktop e menu recolhível no celular. Alternativa: navegação lateral para gestão, mantendo cabeçalho e rodapé inspirados nas referências.
- Não houve escolha final do modelo de navegação.

### Navegação e rodapé — decisão do usuário

- Escolhida a opção A: navegação superior, conforme comparação visual.
- O usuário não solicita outros ajustes de layout neste momento.
- Texto do rodapé: “Julib — Sua biblioteca, bem organizada”.
- Exibir a homenagem à Juliana Mendes em um link; interpretação adotada para o protótipo: “Uma homenagem à Juliana Mendes”, apontando para a seção de homenagem na página Sobre.
- Manter o nome completo Juliana Mendes na homenagem.

### Homenagem no rodapé — esclarecimento do usuário

- O acesso à homenagem pode ficar no link Sobre ou no próprio nome Julib; não é necessário um link separado “Uma homenagem à Juliana Mendes”.
- Interpretação adotada: nome Julib clicável no rodapé levando à seção de homenagem na página Sobre, mantendo a frase “Julib — Sua biblioteca, bem organizada”.
- A homenagem à Juliana Mendes permanece no conteúdo da página Sobre.

### Consolidação para revisão — 2026-11-03

- Documento consolidado em docs/superpowers/specs/2026-11-03-julib-design.md.
- Revisão independente concluída; pendente aceitar destino operacional privado para backups.
- Decisões técnicas propostas estão identificadas no documento e não representam implementação iniciada.

### Destino dos backups — decisão do usuário em 04/11/2026

- Aceito um repositório privado separado para os backups criptografados.
- Todo o código permanece no único monorepositório público.
- A autorização resolve a escolha do destino; nenhum repositório remoto foi criado nesta etapa.

### Referência adicional de cores — 04/11/2026

- Usuário solicitou analisar https://comunidadesiloe.com.br/ como possível referência de paleta.
- Inspeção do HTML e da página renderizada encontrou verde profundo #053227, verde #074e3d, âmbar #ffbd59 (também #ffbe5a), dourado #daaa60, creme #fffaf4 e branco #ffffff. Esses valores são cores presentes no site, não uma especificação oficial de design tokens.
- Proposta: usar verde profundo como primária e âmbar como destaque, creme no fundo claro e superfícies brancas; manter Inter e navegação já escolhidas.
- Tema escuro precisará ser derivado para o Julib; não foi identificado um seletor de tema claro/escuro no site analisado. Garantir contraste por função, especialmente com âmbar.
- A nova paleta está em avaliação; não substitui o tema aprovado até escolha do usuário.

### Prévia da paleta Siloé — 04/11/2026

- Aplicada ao protótipo para avaliação, sem aprovação definitiva: verde #053227, âmbar #FFBD59, dourado #DAAA60, creme #FFFAF4.
- Tema escuro derivado: fundo #0B1915, superfície #142A23, texto #FFFAF4 e links verde-claro #83C6A7.
- Mantidos menu superior e rodapé escolhidos.
- Artefato local: .superpowers/brainstorm/79723-1793813939/content/siloe-palette.html.

### Paleta e tema inicial — decisão do usuário em 04/11/2026

- Aprovadas as cores da prévia inspirada no site Siloé, substituindo a paleta anterior.
- Seguir o tema do sistema quando possível; usar escuro quando não houver preferência detectável.
- Manter alternância manual; proposta de seletor Claro/Escuro/Sistema persistido no dispositivo.
- Documento consolidado atualizado com os valores claros e escuros aprovados.

### Implementação iniciada e revisão — 04/11/2026

- Alterações locais do usuário consolidadas no desenho; autorizada a implementação.
- Código, testes e documentação produzidos conforme plano; registro de estado em docs/implementation-status.md.
- Repositórios Julib público e Julib-backups privado criados.
- Projeto Supabase Julib criado na organização IFC após aceite explícito, com cotação mensal zero.
- Contas autorizadas recebidas e configuradas somente no arquivo privado, sem publicá-las no levantamento.

### Prioridade de evolução — 06/11/2026

O usuário decidiu consolidar primeiro o uso da aplicação por Marco e Juliana, antes da abertura para outras pessoas. A sequência recomendada para essa consolidação é melhorar detalhes/edição dos livros e, depois, painel/empréstimos. Múltiplas bibliotecas e convites ficam para uma etapa posterior. O desenho das novas telas e eventuais campos adicionais ainda serão discutidos; essa escolha não aprova automaticamente um layout ou mudança de dados.
