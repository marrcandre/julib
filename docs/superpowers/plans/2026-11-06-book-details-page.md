# Book Details Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement inline, with one final review.

**Goal:** Substituir modais de detalhes/edição por página privada com URL própria e capa editável no mesmo fluxo.
**Architecture:** Books continua responsável pelo catálogo/cadastro e passa a expor links. BookDetails concentra consulta e ações de exemplares; BookEditor concentra rascunho/capa e edição atômica via PUT compatível. Query do catálogo e scrollBehavior preservam contexto.
**Tech Stack:** Django/Ninja, Vue3/TS/PrimeVue, PostgreSQL existentes, sem dependências novas.
**Spec:** docs/superpowers/specs/2026-11-06-book-details-design.md

## Global Constraints

- Somente planos gratuitos; sem migrações ou novos campos bibliográficos.
- URL privada e isolamento por biblioteca; histórico de empréstimos nunca é apagado.
- JPEG/PNG/WebP máximo5MiB; origem/atribuição preservadas.
- Actions pausado; backup cifrado e recuperação antes da publicação manual.

## Review Focus

- URL direta inválida/estrangeira e troca rápida de ID não mostram dados anteriores.
- Falha de validação/upload não aplica metadados/capa parcialmente; retry não envia outra imagem desnecessariamente.
- Cancelar e sair com alterações não gravam o livro; navegação/retorno preserva contexto.
- Desejados e exemplares anteriores preservam histórico e idempotência de aquisição.
- Cadastro via câmera e novas abas continuam funcionais e acessíveis.

### Task 1 — Backend de edição atômica

Files: schemas.py, api.py, services.py; tests/test_book_edit.py.
Interface: PUT /books/:id aceita cover_public_id opcional e retorna BookOut.
- [x] RED: testes de sucesso conjunto, rollback por campo inválido, capa estrangeira, isolamento e URL manual limpando cover_id.
- [x] Implementar confirmação transacional preservando contratos existentes; GREEN e gerar schema.

### Task 2 — Página e navegação

Files: pages/BookDetails.vue, components/BookEditor.vue, book-details.css; main.ts, Books.vue, Dashboard.vue; e2e/book-details.spec.ts.
- [x] RED: rota direta, âncoras/nova aba, edição e capa local/cancelamento, retorno ao catálogo.
- [x] Implementar página/editor e ações de exemplares; remover detalhes/edição antigos do catálogo.
- [x] Filtros na query, retorno seguro e rolagem; compatibilidade ?livro=.
- [x] Atualizar jornadas afetadas e preservar câmeras, filtros/densidade, toasts e desejados.

### Task 3 — Verificação e publicação

- [x] make check-local e suíte Playwright em PostgreSQL descartável; conferir desktop e celular320/393px.
- [x] Revisão focada do diff, corrigir achados com teste.
- [x] PR/integrar; backup privado cifrado com restore verificado, publicação manual backend/frontend e smoke somente leitura em produção.
- [x] Registrar evidências, limitações e servidores locais restaurados.

Ledger: backend RED→GREEN para edição atômica, URL manual e isolamento. Playwright RED em /livros/1 antes da rota, GREEN após implementar. Retorno/nova aba/rascunho de capa e validação de saída cobertos. make check-local:66backend/11Vitest; suíte completa19Playwright passou. Ajuste de teste: aguardar reclassificação terminar antes de navegar, pois a proteção de saída bloqueia navegação durante gravação. QA visual real com APIs simuladas em1366/393/320px passou, inclusive tema claro, histórico e exclusão bloqueada; sem overflow/erro JS. Nova tag propagada ao contexto do editor para reaparecer ao reabrir. Sem migrações nesta entrega.

Ruling de revisão: manter Cancelar imediato como na prévia aprovada. A confirmação de saída cobre navegação/fechar/atualizar, não a ação explícita de descartar. Redação do spec esclarecida. Nenhuma alteração de comportamento na revisão. Teste real adicional cobre edição bibliográfica/exemplar e bloqueio de exclusão após empréstimo devolvido; seletor de localização identificado pelo nome acessível para distingui-lo de Dar baixa.

Verificação final:66backend/11Vitest/21Playwright aprovados, incluindo edição de exemplar e preservação do empréstimo devolvido em API real descartável. Nova jornada RED→GREEN para next do login em URL direta. Preparado backup cifrado manual-20261106T131326Z com237capas, baixado/restaurado, contagens iguais; nenhum registro real alterado. Sem DDL nesta publicação.

Concluído: PR14 integrado em7116330 e ambos os projetos Vercel publicados, sem migração. Verificação pública:3jornadas simuladas adicionais e QA visual em1366/393/320px aprovados; API privada/Swagger/prontidão corretos. Acervo/contagens/RLS/grants preservados em leitura. Backup manual remoto cifrado restaurado antes de publicar, servidores locais restaurados. Evidências em docs/implementation-status.md. Sem trabalho obrigatório restante nesta entrega.
