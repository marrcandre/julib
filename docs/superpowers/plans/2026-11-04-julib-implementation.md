# Julib Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Entregar a primeira versão local utilizável e preparar integrações/deploy sem inventar credenciais de produção.
**Architecture:** Monólito modular Django com Ninja e PostgreSQL; SPA Vue/PrimeVue em origem única via proxy. Regras transacionais em services reutilizados pelo Admin.
**Tech Stack:** Python 3.13, Django 5.2 LTS, Ninja, allauth, psycopg, uv; Vue 3, PrimeVue 4 (MIT), Vite, TypeScript, npm; pytest, Vitest, Playwright.
**Spec:** docs/superpowers/specs/2026-11-03-julib-design.md

## Global Constraints

- Somente planos gratuitos; nenhum segredo no repositório público.
- Contas Google em allowlist; Admin e Swagger somente Marco.
- Biblioteca como limite de autorização, três datas de empréstimo e histórico preservado.
- Paleta Siloé, menu superior, Sistema/Claro/Escuro com fallback escuro.
- Dados externos editáveis, importação idempotente, sem operação offline.
- Testes primeiro; produção somente após CI no mesmo commit.

## Review Focus

- Requisição alterada para apontar relações de outra biblioteca deve ser recusada (tarefa 2/3).
- Reenvio simultâneo de empréstimo/importação não deve duplicar registros (tarefa 3/5).
- ISBN-10 e ISBN-13 equivalentes exigem confirmação de exemplar (tarefa 2).
- Falta de câmera/API/conexão mantém cadastro manual e erro honesto (tarefa 4/6).
- Logout/revogação não deixa dados privados em cache (tarefa 1/5/6).

## Estrutura

backend/config: settings, URLs, WSGI. backend/library: modelos, schemas, services, API, Admin, adapters e comandos. backend/tests: regras e HTTP. frontend/src: layout, tema, cliente e páginas. scripts: verificação e backup. docs: operação. .github/workflows: CI/deploy.

### Task 1: Fundação autenticada

**Files:** backend/pyproject.toml, config/{settings,urls}.py, library/{models,auth,api}.py, tests/test_access.py; .gitignore, compose.yaml.
**Interfaces:** produz User, Library, Membership; GET /api/v1/session, /health; sessão Django; require_library(request) -> Library.
- [ ] Escrever testes: health público; sessão anônima 401; usuário fora da allowlist 403; membro autorizado 200; documentação/admin recusam membro comum.
- [ ] Rodar pytest e observar falha; configurar dependências e implementar mínima fundação, Google allauth e CSRF.
- [ ] Rodar pytest tests/test_access.py, check e migrações; esperado verde. Commit.

### Task 2: Acervo e locais

**Files:** library/{models,services,schemas,catalog_api,admin}.py, tests/test_catalog.py.
**Interfaces:** create_book(library, data), add_copy(library, book_id,...), move_location(library,...); rotas /books, /copies, /locations, /tags e /dashboard.
- [ ] Testes: ISBN equivalente, confirmação de duplicata, aquisição padrão, número único, ciclo/local estrangeiro recusado, filtro de tag/local, lote atômico, disponibilidade.
- [ ] Observar vermelho, implementar modelos/migrações/services, serializers explícitos e paginação; Admin acessível desde os modelos novos.
- [ ] Rodar pytest tests/test_catalog.py e suite; esperado verde. Commit.

### Task 3: Circulação

**Files:** library/{circulation,schemas,api,admin}.py; tests/test_loans.py.
**Interfaces:** lend(library, copy_id, person_id, start, due), return_loan(...), retire_copy(...); /people, /loans, /copies/{id}/retire.
- [ ] Testes: nome/telefone obrigatórios, mês calendário, uma operação aberta por exemplar, relações estrangeiras, perda sem devolução, baixa bloqueada, histórico.
- [ ] Observar vermelho; implementar constraints, lock e services; Admin usa as operações e campos protegidos.
- [ ] Rodar pytest tests/test_loans.py e suite; esperado verde. Commit.

### Task 4: Provedores e mídia

**Files:** library/{providers,media}.py, tests/test_providers.py.
**Interfaces:** search_books(query) -> list[BookCandidate]; assinatura e confirmação autenticadas de upload.
- [ ] Testes com HTTP simulado: timeout/quota/fallback, ISBN inválido, upload só em pasta autorizada/formato/tamanho aceitos.
- [ ] Observar vermelho; implementar Google Books/Open Library, metadados de origem e upload assinado Cloudinary, sem segredo no cliente.
- [ ] Rodar testes focados e suite; esperado verde. Commit.

### Task 5: Importação e compartilhamento

**Files:** library/{imports,sharing}.py, tests/{test_imports,test_sharing}.py.
**Interfaces:** prévia CSV, seleção/ação por linha, lotes de 25 idempotentes; /share/manage e /public/{token}/books.
- [ ] Testes: BOM/ISBN formatado pelo Excel, limite 3 MB/5.000 linhas, lote repetido, já cadastrado ignorado, cópia explícita, token revogado, ausência de campos privados.
- [ ] Observar vermelho; implementar parsing, persistência, transações e schemas públicos; limpeza após sete dias por comando.
- [ ] Rodar testes e suite; esperado verde. Commit.

### Task 6: Interface responsiva online

**Files:** frontend/package.json, vite.config.ts, src/{App.vue,main.ts,theme.ts,api.ts}, src/pages/*.vue, tests/*.test.ts, public/manifest.webmanifest.
**Interfaces:** cliente para contratos das tarefas 1–5; proxies locais e views /, /livros, /emprestimos, /locais, /importar, /sobre, /colecao/:token.
- [ ] Testes primeiro: tema Sistema/Claro/Escuro, erros HTTP, sessão e consulta pública; observar vermelho.
- [ ] Implementar header/footer aprovados, dashboard real, CRUD, seleção de locais em lote, empréstimos, revisão de CSV, compartilhamento, câmera contínua com confirmação e fallback manual, upload e Sobre/PIX.
- [ ] PWA online com manifesto/ícones sem cache privado; testar build, componentes e jornada ponta a ponta em viewport móvel/desktop.
- [ ] Rodar npm test e npm run build, esperado verde. Commit.

### Task 7: Operação e entrega

**Files:** README.md, LICENSE, CONTRIBUTING.md, .env.example, Makefile, scripts/*, .github/workflows/{ci,deploy}.yml, docs/operations.md, ops/backup-workflow.yml.example.
**Interfaces:** make check, compose PostgreSQL local; deploy workflow após CI; backup template para repo privado.
- [ ] Testar export/import de backup com PostgreSQL temporário e dados sintéticos; tamanho/cotas medidos só com credenciais reais.
- [ ] Implementar documentação de Google/Supabase/Cloudinary/Vercel, workflow CI PostgreSQL e frontend; deploy desabilitado até configurar vars/secrets.
- [ ] Preparar backup diário cifrado e sete dias somente no repositório privado; documentar chave e restauração, mídia e limitações de ativação.
- [ ] Rodar checks, migrações sem alterações e smoke real. Revisão independente do conjunto; corrigir problemas relevantes com teste RED→GREEN.

## Registro de execução

Credenciais OAuth, Cloudinary, Supabase e projetos Vercel serão configuradas na etapa externa. A falta delas não impede implementar/testar localmente; produção e backup real não serão declarados ativos sem verificação.
