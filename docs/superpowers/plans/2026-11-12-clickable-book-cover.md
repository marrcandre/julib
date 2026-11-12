# Capa clicável — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Abrir o seletor de imagem ao clicar na capa na edição de livros.

**Architecture:** Reutilizar o input e o fluxo de seleção e salvamento de BookEditor.vue. Acrescentar um botão envolvendo a prévia e um lápis decorativo, com estilos locais à página de detalhes.

**Tech Stack:** Vue, TypeScript, CSS, Playwright e Vitest.

**Spec:** docs/superpowers/specs/2026-11-12-clickable-book-cover-design.md

## Global Constraints

Manter o botão “Trocar capa”, os formatos JPG, PNG e WebP e o limite de 5 MB. Sem alterações no backend ou publicação.

## Review Focus

Sem capa: o placeholder também abre o seletor. Teclado: Enter e espaço ativam a ação. Salvamento em andamento: controle desabilitado. Celular: lápis visível sem hover. Cancelamento: preservar o descarte da prévia existente.

### Task 1: Controle acessível sobre a capa

**Files:** modificar frontend/src/components/BookEditor.vue, frontend/src/book-details.css e frontend/e2e/book-details.spec.ts.

**Interfaces:** consumir fileInput?.click(), preview e busy existentes; preservar selectFile, clearFile e save sem mudar contratos.

- [x] Estender o teste de edição para abrir o seletor pela capa com clique e teclado, com e sem imagem, mantendo o botão existente; verificar desabilitação durante salvamento e descarte ao cancelar.
- [x] Executar o teste e confirmar falha pela ausência do controle.
- [x] Envolver a prévia e o placeholder em botão type="button", com nome acessível “Trocar capa”, title, disabled ligado a busy e lápis decorativo sempre visível.
- [x] Estilizar o botão sem alterar proporções da capa; acrescentar fundo sólido no lápis e estados de hover e foco.
- [x] Executar o teste de edição, npm test e npm run build; conferir desktop e celular em execução local, incluindo visibilidade do lápis sem hover.
- [x] Revisar o diff e relatar resultados; manter alterações locais para avaliação do usuário.

## Resultado da execução

Implementado na branch feat/clickable-book-cover. Teste de interação falhou antes da mudança pela ausência do botão envolvendo a capa e passou depois, incluindo clique, Enter, espaço, prévia e cancelamento. Conferidas capturas desktop e celular. 22 testes unitários e build passaram. Dos quatro testes de detalhes, três passaram; o teste integrado de histórico não conseguiu preparar os dados porque a sessão local está sem autenticação (401) e o cadastro retorna CSRF 403. Revisão independente identificou a variável de cor indefinida no foco, corrigida para --green. Ajustado align-self para evitar esticar a área clicável na grade móvel. Nada publicado.
