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

A busca do catálogo ocorre após 300 ms. Filtros e visualização ficam nos botões ao lado da busca; o menu ⋮ reúne importação, organização de exemplares e compartilhamento. O badge ao lado de Livros mostra a quantidade de edições encontradas.

Em Visualização, o slider ajusta de 3 a 10 livros por linha. Essa densidade fica salva por usuário neste navegador/dispositivo, independente dos outros aparelhos; o padrão inicial é quatro no celular e sete no desktop. Limpar os dados do navegador remove essa preferência local. O modo Somente capas/Cartões/Lista continua associado à conta.
