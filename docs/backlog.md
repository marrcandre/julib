# Melhorias solicitadas

## Roadmap aprovado — 17/11/2026

Ordem aprovada para as próximas evoluções. Este registro define o escopo planejado; não indica que as fases foram implementadas nem autoriza publicação automática ao concluí-las.

### Fase 1 — Convites para criação de bibliotecas

- Permitir que o proprietário da aplicação convide pessoas para criar novas bibliotecas.
- O convidado autentica-se com Google e pode criar sua primeira biblioteca; torna-se automaticamente administrador dela.
- O novo administrador poderá convidar outras pessoas para participar da própria biblioteca.
- Preservar o fluxo atual de convites para ingresso em bibliotecas existentes.

### Fase 2 — Importação de coleções do Libib

- Investigar e documentar os formatos de exportação disponíveis e mapear seus campos para o modelo atual do Julib.
- Apresentar uma prévia antes de importar e identificar duplicidades, especialmente por ISBN.
- Nunca sobrescrever ou excluir registros existentes; considerar importações repetidas e preservar os dados originais sempre que possível.
- Apresentar relatório dos registros importados, ignorados e com erros.

### Fase 3 — Enriquecimento bibliográfico

Adicionar aos livros `subtitle` (subtítulo), `description` (sinopse ou descrição) e `subjects` (assuntos bibliográficos obtidos das APIs). Assuntos são metadados bibliográficos, não tags: não haverá gerenciamento manual nem filtros específicos para assuntos nesta versão. As tags existentes continuam funcionando como hoje.

Preservar dados preenchidos manualmente e aproveitar as integrações existentes com BrasilAPI, Open Library e Google Books. Exibir sinopse expansível e assuntos na ficha do livro.

### Fase 4 — Enriquecimento do acervo existente

Ampliar o comando atual de enriquecimento para oferecer prévia, preencher somente campos vazios e executar apenas após confirmação explícita. Manter a separação entre bibliotecas.

## Edição e notificações — 06/11/2026

Registradas pelo usuário junto da aprovação da paginação; pendentes de implementação nesta próxima etapa:

- [x] Tornar Salvar/Cancelar acessíveis no início da edição, mantendo as ações no final, bloqueio enquanto salva e proteção contra perda de alterações.
- [x] Mover os toasts para o topo à direita, mantendo desaparecimento automático e tamanho compacto no celular.
- [x] Permitir iniciar a edição clicando na capa por um botão acessível por teclado; livros sem capa ou com imagem quebrada recebem ação equivalente. A imagem selecionada continua sendo prévia até salvar.
