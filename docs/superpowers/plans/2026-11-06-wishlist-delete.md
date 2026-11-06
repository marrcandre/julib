# Desejados e exclusão definitiva Implementation Plan

**Goal:** Separar desejos do acervo e excluir cadastros sem qualquer histórico de empréstimo.
**Architecture:** Book.is_desired com default persistente false; metadados permanecem únicos por ISBN/biblioteca. Registration aceita destino wishlist/collection e recibos nullable para impedir retries após remoção. Services transacionais compartilham locks da biblioteca/exemplares. UI existente ganha seletor compacto de lista, destino no cadastro e ações nos detalhes.
**Tech Stack:** Django/Ninja/PostgreSQL, Vue/PrimeVue/TypeScript existentes; sem serviços novos.

Regra confirmada pelo usuário: bloquear exclusão quando qualquer exemplar tiver histórico, inclusive empréstimos já devolvidos. Desejados não são públicos e não entram nos totais físicos. Aquisição cria exemplar e preserva a edição. Reclassificação remove somente exemplares ativos sem histórico; se algum ativo tiver histórico, orientar baixa adequada antes de reclassificar. Exemplares anteriormente baixados e seus históricos ficam preservados. Recebimentos antigos após exclusão retornam erro e não recriam dados; ISBNs continuam únicos. Não executar exclusões reais durante desenvolvimento.

- [x] Escrever/observar testes RED para desejo sem exemplar, aquisição/retry, exclusão com recibos/importação e bloqueio histórico/isolamento/concorrência.
- [x] Implementar migração aditiva: is_desired=false; Registration.book/copy nullable SET_NULL e ImportRow.copy SET_NULL; manter fingerprints legados no destino padrão. Reversão exige preflight de recibos nulos, sem reversão automática/destrutiva.
- [x] Services/API/Admin/query pública e dashboard: transações, ações protegidas e schemas atualizados; testar e gerar tipos.
- [x] UI: acesso compacto a Acervo/Desejados, destino no formulário sem campos físicos no desejo, adquirir/mover/excluir com confirmação reforçada e motivos de bloqueio. Preservar scanner contínuo, preferências, filtros e busca em 300ms.
- [x] Testar fluxos reais e simulados desktop/móvel, histórico/retries/concorrência, Admin e privacidade; revisão focada.
- [ ] CI, PR, publicação com backup prévio, verificação somente leitura do acervo e smoke; registrar evidência.

Estado final desta etapa: implementação e revisão focada concluídas, sem achados importantes. CI/merge/deploy permanecem pendentes porque o GitHub bloqueou Actions antes de iniciar o job por pendência de faturamento da conta. PR #13 preservado, sem alterações de produção. Reexecutar a CI após liberação; não contornar o backup obrigatório.

Atualização autorizada pelo usuário: Actions temporariamente desativado; publicação manual substitui execução remota, com testes locais completos, backup privado cifrado e teste de recuperação antes da migração. Procedimento e retomada registrados em docs/operations.md. Última etapa passa a ser publicação manual verificada enquanto o chamado do GitHub estiver aberto.
