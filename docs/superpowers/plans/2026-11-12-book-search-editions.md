# Busca bibliográfica por edição — implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Descobrir edições e completar páginas, idioma e edição sem misturar versões.
**Architecture:** Consultar dados de edições da Open Library e resultados Google no orçamento existente. Resolver detalhes por ISBN ao complementar; preservar a origem de cada campo.
**Tech Stack:** Django, Python, Vue, TypeScript, pytest e Playwright.
**Spec:** docs/superpowers/specs/2026-11-12-book-search-editions-design.md

## Global Constraints

Preservar valores existentes, consultas limitadas, cadastro manual e funcionamento parcial. Sem atualização em massa ou publicação.

## Review Focus

ISBNs diferentes não se fundem; dados agregados de obras não viram dados de edição; resultados sem ISBN permanecem manuais; respostas malformadas e indisponibilidade preservam outras fontes; detalhes externos nunca geram URLs arbitrárias.

## Task 1 — Adaptadores e enriquecimento

- [x] Adicionar testes de candidatos por edição, deduplicação, fallback, detalhes por ISBN, idioma/edição e preservação de campos.
- [x] Confirmar falha e implementar em backend/library/providers.py.
- [x] Rodar testes backend e verificações de tipos/formatação.

## Task 2 — Escolha na interface

- [x] Mostrar informações editoriais e indicação de ISBN ausente na lista de frontend/src/pages/Books.vue.
- [x] Ampliar frontend/e2e/api-enrichment.spec.ts para verificar apresentação, preenchimento e salvamento.
- [x] Executar testes frontend, E2E relevante e build; revisar o diff e manter local.

Execução direta nesta sessão, autorizada pelo usuário ao aprovar o desenho e solicitar implementação.

## Validação e decisões

Consultas de descoberta retornam no máximo 24 candidatos e fazem no máximo quatro consultas de detalhes, dentro do orçamento existente de 18 segundos. A consulta Google precede os detalhes para preservar o fallback. A API Open Library retorna uma edição relevante por obra; Google acrescenta candidatos, sem prometer listar todas as edições. Resultados sem ISBN continuam disponíveis para preenchimento manual.

Testes novos falharam antes da implementação e passaram depois. Revisão independente identificou chaves de autor malformadas que poderiam interromper a busca; regressão reproduzida e corrigida. O endpoint de detalhes por ISBN utiliza jscmd=details, evitando depender de redirecionamento em /isbn/. A consulta real por título retornou idioma, edição e ISBN. Os 22 testes frontend, os três E2E de enriquecimento e o build passaram. Ruff e mypy com a configuração do backend passaram. Nenhum cadastro existente foi atualizado em massa, nenhum deploy realizado.
