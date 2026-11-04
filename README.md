# Julib

Aplicação: [julib.vercel.app](https://julib.vercel.app) · acesso com Google restrito às contas autorizadas.


**Sua biblioteca, bem organizada.**

Biblioteca pessoal compartilhada, criada por Marco André Mendes em homenagem à Juliana Mendes. Cadastro por edição e exemplares, localizações até a prateleira, tags livres e controle de empréstimos com histórico. Tema claro/escuro inspirado na Siloé, menu superior e interface responsiva.

## Funcionalidades

- Cadastro manual, busca Google Books/Open Library e leitura de ISBN pela câmera.
- Importação CSV do Goodreads com seleção, reimportação segura e progresso por lote.
- Cópias idênticas com número interno, aquisição e localização próprios.
- Localizações hierárquicas e mudanças em lote; tags e filtros.
- Pessoas, empréstimos, devoluções, atrasos e baixa por perda/venda/doação.
- Catálogo somente leitura por link revogável, sem localização ou dados de pessoas.
- Login Google com allowlist; Admin e Swagger restritos à conta administrativa.
- PWA online, página Sobre, projetos relacionados e apoio por PIX.

## Stack

Python 3.13, Django 5.2 LTS, Django Ninja, uv, PostgreSQL; Vue 3, TypeScript, PrimeVue 4, Vite e npm. Código em um monorepositório MIT. Destinos planejados: Vercel, Supabase e Cloudinary nos planos gratuitos.

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
- [Levantamento e decisões](docs/discovery/2026-11-03-biblioteca-pessoal.md)
- [Configuração, deploy, backup e recuperação](docs/operations.md)

Integrações externas precisam de contas e credenciais próprias. Workflows e scripts preparados não significam que produção ou backups estejam ativos; consulte o registro operacional antes de usar dados reais.

## Autor e projetos

Marco André Mendes · [GitHub](https://github.com/marrcandre) · [LinkedIn](https://www.linkedin.com/in/marrcandre/)

Conheça [Dons Espirituais](https://dons-espirituais.vercel.app) e [Cinco Ministérios](https://cinco-ministerios.vercel.app).

MIT. Apoio voluntário via PIX está disponível na página Sobre.
