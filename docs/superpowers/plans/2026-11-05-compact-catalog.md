# Catálogo compacto Implementation Plan

> Executar inline com superpowers:executing-plans e TDD; autorização do usuário inclui implementação/publicação do desenho aprovado.

**Goal:** Reduzir a área anterior aos livros, mantendo todos os fluxos existentes.
**Architecture:** Controles em CatalogToolbar Vue, página Books conserva operações. Cabeçalho global compacto com drawer. Densidade local por user_id; modo mantém API atual. GET autenticado de estado de compartilhamento sem token.
**Tech Stack:** Django Ninja, Vue/TypeScript/PrimeVue, Vitest/Playwright/PostgreSQL existentes.

- [x] Contratos e preferências: testes falhando para user_id e estado de link privado, helper de densidade isolado por usuário/storage; implementar e regenerar OpenAPI.
- [x] Controles compactos: teste de layout/fluxos falhando; criar CatalogToolbar com menus, filtros em rascunho, modos/slider e badge; integrar sem mudar operações.
- [x] Cabeçalho, avisos e compartilhamento: drawer móvel, Toast e diálogo de gestão de link; preservar confirmações/CSRF e câmera.
- [x] Atualizar jornadas aos novos pontos de entrada sem perder provas anteriores; testar dois contextos/dispositivos e dois usuários, teclado/slider, filtro aplicado uma vez e compartimento sem mutação.
- [x] Executar make check-local, E2E completo no banco descartável e inspeção visual móvel/desktop; revisão focada; corrigir falhas justificadas.
- [ ] PR, CI, merge e publicação automática com backup; conferir interface publicada com dados de teste e saúde; registrar evidências finais.

## Evidência local

RED registrado para identidade/estado de link, helper ausente e primeira capa abaixo da meta. GREEN: 55 backend, 9 Vitest, tipos/build e 14 E2E no PostgreSQL descartável. Revisão independente focada sem achados importantes. QA com amostra bibliográfica somente leitura confirmou primeira capa móvel em 187 CSS px, sem erros JS/overflow. Testes adicionais garantem painéis móveis encostados à borda inferior. Servidores locais normais restaurados após E2E.
