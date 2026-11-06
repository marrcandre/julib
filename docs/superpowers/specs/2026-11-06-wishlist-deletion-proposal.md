# Livros desejados e exclusão definitiva — decisões confirmadas

Data: 06/11/2026. Pedido: permitir excluir cadastros definitivamente e manter livros cadastrados que ainda não pertencem ao acervo. Estado: implementação autorizada. O usuário confirmou bloquear a exclusão definitiva quando existir qualquer histórico de empréstimo, inclusive devolvido.

## Abordagem proposta

Reutilizar Livro/Edição para metadados, ISBN, páginas, tags, capa e origem. Acrescentar marca de desejado; não criar exemplar físico ao cadastrar um desejo. Uma entidade bibliográfica única evita duplicar a edição e perder correções ao adquirir o livro. Lista separada do acervo, com acesso compacto compatível com o layout recém-aprovado; desejados não entram nos totais físicos nem no link público.

Cadastro por busca/câmera/manual permite escolher Acervo ou Desejados. Adquirir um desejado cria exemplar com localização e data de aquisição e o retira dos desejados, na mesma transação. Reclassificar livro atual exige conferir exemplares e histórico; exemplares efetivamente anteriores e seus empréstimos não devem desaparecer silenciosamente. Para cadastro equivocado sem histórico, é possível remover os exemplares indevidos e manter a edição nos desejados, após confirmação explícita.

Exclusão nos detalhes deve apresentar livro, quantidade de exemplares e consequências antes da confirmação reforçada. Regra confirmada: excluir edição e exemplares somente sem qualquer histórico de empréstimo; quando houver, usar baixa/arquivo para preservar o histórico. Não apagar histórico de empréstimos. Implementar o recurso não equivale a executar exclusões em produção.

## Integridade técnica a preservar

- Mesmo ISBN continua representando uma única edição por biblioteca, com confirmação para cópias. Livro desejado deve ser encontrado na verificação de duplicidade ao cadastrar/adquirir.
- Cadastros e aquisições permanecem idempotentes. Exclusão não pode permitir que uma repetição antiga recrie exemplares; recibos técnicos devem registrar remoção sem conservar vínculo obrigatório ao cadastro excluído. Preservar compatibilidade dos fingerprints de operações anteriores ao novo campo de destino.
- ImportRow atualmente protege Copy e Registration protege Book/Copy. A migração precisa tratar essas referências sem apagar outros livros, sessões de importação ou histórico. Linhas concluídas não devem ser reimportadas automaticamente depois de excluir o livro.
- Operações transacionais e isoladas por biblioteca; bloqueio de empréstimo/exclusão concorrentes. Não permitir desejado com exemplar ativo disponível para empréstimo.
- Livro desejado pode preservar exemplares anteriormente baixados e seu histórico, mas não deve ser tratado como exemplar atualmente possuído.
- Sem exclusão automática de ativos Cloudinary compartilhados. Backups continuam seguindo a retenção operacional existente.
- Migrações aditivas/compatíveis, backup antes da publicação e testes de reversão lógica dos fluxos; nenhuma alteração direta de registros reais durante o desenvolvimento.

## Aceite sugerido

Criar desejado sem exemplar, pesquisar/editar/excluir desejo, adquirir sem duplicar edição, reclassificar cadastro elegível, excluir cadastro elegível com confirmação, bloquear relações de outra biblioteca, preservar/restringir histórico conforme decisão explícita e impedir recriação por retry de cadastro/importação após exclusão. Conferir totais, empréstimos e catálogo compartilhado nos três estados.
