# Julib

Aplicação: [julib.vercel.app](https://julib.vercel.app) · acesso com Google restrito às contas autorizadas.


**Sua biblioteca, bem organizada.**

Biblioteca pessoal compartilhada, criada por Marco André Mendes em homenagem à Juliana Mendes. Cadastro por edição e exemplares, localizações até a prateleira, tags livres e controle de empréstimos com histórico. Tema claro/escuro inspirado na Siloé, menu superior e interface responsiva.

## Funcionalidades

- Cadastro manual, busca Google Books/Open Library, alternativa BrasilAPI/CBL para ISBN e leitura pela câmera.
- Importação CSV do Goodreads com seleção, reimportação segura e progresso por lote.
- Cópias idênticas com número interno, aquisição e localização próprios.
- Localizações hierárquicas e mudanças em lote; tags e filtros.
- Pessoas, empréstimos, devoluções, atrasos e baixa por perda/venda/doação.
- Catálogo somente leitura por link revogável, sem localização ou dados de pessoas.
- Login Google com allowlist; Admin e Swagger restritos à conta administrativa.
- PWA online, página Sobre, projetos relacionados e apoio por PIX.

## Stack

Python 3.13, Django 5.2 LTS, Django Ninja, uv, PostgreSQL; Vue 3, TypeScript, PrimeVue 4, Vite e npm. Código em um monorepositório MIT. Hospedagem configurada na Vercel, Supabase e Cloudinary, nos planos gratuitos.

## Executar localmente

Requisitos: uv, Node 22, Docker Compose (ou PostgreSQL local). Nunca use banco de produção nos testes.

```sh
test -f .env || cp .env.example .env
test -f .env.local || cp .env.local.example .env.local
# Edite as credenciais privadas de Google/Cloudinary em .env.
make setup
make db
make migrate-local
make bootstrap-local
make backend-local
# Em outro terminal:
make frontend
```

Abra http://127.0.0.1:5173. Configure Google OAuth conforme [operação](docs/operations.md) para entrar. Os comandos `*-local` carregam `.env` e depois `.env.local`, usando o PostgreSQL Docker mesmo se houver uma URL do Supabase exportada no shell. O banco é obrigatório; não há fallback SQLite. O frontend encaminha API, OAuth e Admin para o Django local.

Admin: `/admin/`. Swagger: `/api/v1/docs`. Ambos exigem a conta administrativa autorizada. Provisione a biblioteca antes do primeiro login; as contas permitidas são associadas ao entrar. Nenhum cadastro aberto ou login alternativo de produção.

## Verificar

```sh
make check-local
# Crie uma vez o banco descartável de E2E:
docker compose exec db createdb -U julib julib_e2e
make e2e-local
```

`make check` executa lint, formatação e tipos Python, checks Django/migrações, pytest no PostgreSQL, Vitest, TypeScript e build. O E2E cria apenas uma sessão de teste no banco configurado, sem rota de login alternativa. Instale Chromium antes: `npx --prefix frontend playwright install chromium`. Pare servidores nas portas 8000/5173 antes de rodar `make e2e`.

## Documentação

- [Requisitos e arquitetura aprovados](docs/superpowers/specs/2026-11-03-julib-design.md)
- [Plano de implementação](docs/superpowers/plans/2026-11-04-julib-implementation.md)
- [Verificação de requisitos e próximas entregas](docs/reviews/2026-11-05-requisitos-e-proximas-entregas.md)
- [Levantamento e decisões](docs/discovery/2026-11-03-biblioteca-pessoal.md)
- [Configuração, deploy, backup e recuperação](docs/operations.md)

Integrações externas precisam de contas e credenciais próprias. Workflows e scripts preparados não significam que produção ou backups estejam ativos; consulte o registro operacional antes de usar dados reais.

## Autor e projetos

Marco André Mendes · [GitHub](https://github.com/marrcandre) · [LinkedIn](https://www.linkedin.com/in/marrcandre/)

Conheça [Dons Espirituais](https://dons-espirituais.vercel.app) e [Cinco Ministérios](https://cinco-ministerios.vercel.app).

MIT. Apoio voluntário via PIX está disponível na página Sobre.

## Cadastro pela câmera

Em Livros → + (Adicionar livro) → Escanear ISBN, permita o acesso e aponte para o código de barras ISBN (normalmente EAN-13, começando por 978 ou 979). O navegador prefere a câmera traseira e consulta os dados automaticamente ao reconhecer um ISBN válido. Escolha o resultado, confira os campos e pressione Salvar e continuar; reconhecer o código não cadastra o livro sozinho. Ler outro código libera uma nova tentativa. Se não houver resultado, use a busca manual ou preencha os campos. Fechar a janela desliga a câmera.

A imagem é processada no navegador; a busca envia o ISBN, sem enviar vídeo ou fotos. A câmera exige permissão do navegador e acesso por HTTPS (ou localhost em desenvolvimento). Leitura de texto/fotografia da capa não faz parte desse recurso.

## Consulta do acervo

A busca do catálogo ocorre após 300 ms. Filtros e visualização ficam nos botões ao lado da busca; o menu ⋮ reúne importação, organização de exemplares e compartilhamento. O badge ao lado de Acervo/Desejados mostra a quantidade de edições encontradas.

Em Visualização, o slider ajusta de 3 a 10 livros por linha. Essa densidade fica salva por usuário neste navegador/dispositivo, independente dos outros aparelhos; o padrão inicial é quatro no celular e sete no desktop. Limpar os dados do navegador remove essa preferência local. O modo Somente capas/Cartões/Lista continua associado à conta.

### Desejados e exclusão de livros

Na página **Livros**, o seletor **Acervo / Desejados** separa os livros possuídos dos que você quer adquirir. Ao cadastrar por câmera, busca ou manualmente, escolha o destino em **Salvar em**. Desejados guardam capa, ISBN, páginas e tags, sem criar exemplar ou aparecer no link público.

Após entrar, a página principal é **Livros**. A identificação da biblioteca e o título da aba usam o nome configurado pelo administrador técnico; o menu da conta reúne as opções **Claro** e **Escuro**.

Nos detalhes de um desejado, **Adicionar ao acervo** pede localização e data de aquisição e cria um exemplar da mesma edição. Para corrigir um cadastro do acervo, **Mover para desejados** remove os exemplares ativos sem histórico após confirmação; exemplares baixados e seus históricos permanecem preservados. Se um exemplar ativo já teve empréstimo, registre sua baixa apropriada antes de mover o livro.

**Excluir definitivamente**, nos detalhes, exige digitar `EXCLUIR` e remove a edição e seus exemplares. Qualquer empréstimo anterior, inclusive devolvido, bloqueia a exclusão. Repetir um cadastro ou lote de importação já concluído não recria um livro excluído. Arquivos de capa não são apagados automaticamente do Cloudinary, para preservar referências compartilhadas; backups seguem a retenção de sete dias.

### Detalhes e edição do livro

Cada livro tem página própria em `/livros/ID`. Os livros no catálogo são links: podem ser abertos em outra aba, favoritados ou recarregados. O acesso continua privado, com login Google e validação da biblioteca. Links antigos com `?livro=ID` redirecionam para a página nova.

A consulta mostra a ficha completa, capa e exemplares em cartões. **Editar livro** permite alterar dados e capa juntos; selecionar um arquivo só cria uma prévia local. **Salvar alterações** envia a imagem e confirma o vínculo com os metadados na mesma transação. Falha de validação mantém o rascunho para correção e não aplica parcialmente a edição. **Cancelar** descarta explicitamente o rascunho; navegar ou fechar a aba com alterações pede confirmação. Um lápis sobre a capa indica o acesso à edição e, durante a edição, permite escolher outra imagem. Os botões **Cancelar** e **Salvar alterações** são iguais no início e no final do formulário; a posição e o tamanho da capa são preservados ao alternar os modos.

Localização e data de aquisição são editadas no exemplar, separadamente da edição bibliográfica. Histórico informa inclusive quando não há empréstimos. Baixa, reativação, aquisição de desejado e exclusão protegida continuam disponíveis. **Mais ações** reúne mover para desejados e excluir. Voltar ao catálogo preserva busca, filtros, página, visualização e posição na navegação da mesma aba.

### Prioridade das fontes e créditos

Buscas por título combinam candidatos da Open Library e Google Books e mostram ISBN, editora, ano, idioma e edição disponíveis para conferência. Os detalhes bibliográficos vêm de edições específicas; candidatos sem ISBN continuam disponíveis para preenchimento manual. A busca e o complemento por ISBN priorizam BrasilAPI com CBL/Mercado Editorial, Open Library e Google Books, preenchendo campos vazios e preservando valores existentes. A Open Library também fornece idioma e nome da edição quando disponíveis. Erro ou resposta inválida de uma fonte permite tentar a próxima, dentro dos limites de tempo e de consultas. A procura legada de capas prioriza Open Library e usa Google como alternativa.

Créditos opcionais dos provedores não aparecem no catálogo. A origem dos dados permanece registrada internamente. Quando conteúdo Google é usado, sua atribuição obrigatória é mantida e identificada como **Dados bibliográficos** ou **Capa**. Uma foto enviada ao Cloudinary não recebe o crédito da capa anterior; trocar a foto não altera a procedência dos dados bibliográficos. A avaliação de fontes está em `docs/reviews/2026-11-06-fontes-api-creditos.md`.

### Identidade da biblioteca

O topo e o menu móvel exibem o nome cadastrado da biblioteca. Nomes longos são abreviados no cabeçalho, com nome completo no menu e no título do link. Em coleções compartilhadas, aparece o nome da biblioteca daquele link; antes do login, a identificação permanece Julib. O rodapé usa **Powered by Julib** e a apresentação do projeto fica em **Sobre**. Nesta etapa, o administrador continua alterando o nome pelo Django Admin; gestão de proprietários e seleção de biblioteca ativa ficam para uma entrega futura.
