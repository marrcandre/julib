# Página de detalhes e edição do livro — desenho aprovado

O usuário aprovou a proposta e a prévia navegável, pediu URL própria com abertura em outra aba e autorizou implementar em 06/11/2026. Objetivo: consolidar o uso por Marco e Juliana. Painel, empréstimos como página e múltiplas bibliotecas/convites ficam fora desta entrega.

## Abordagens e escolha

Foram apresentadas página única alternando consulta/edição e páginas separadas de detalhes/formulário. Escolhida a primeira, para manter contexto e reunir dados e capa. A prévia é descartável, com dados ilustrativos; a implementação usa os componentes Vue/PrimeVue existentes, as cores aprovadas e Inter.

## Experiência aprovada

- Cada livro tem rota privada `/livros/:id`. Links reais no catálogo e painel permitem nova aba, favorito e atualização direta. Autorização continua no backend por biblioteca; nenhum acesso público novo. Se a sessão estiver encerrada, o login preserva a URL de destino para voltar ao livro.
- Consulta mostra capa, título, autores, acervo/desejado, tags e ficha completa: ISBN, editora, edição, ano, idioma e páginas. Ausências são indicadas como não informado. Atribuição de fonte preservada.
- Editar livro alterna a própria página para campos editáveis e troca de capa. Seleção de arquivo fica local até salvar; Cancelar não altera o livro. Salvar confirma metadados e vínculo da capa conjuntamente. Formatos JPEG/PNG/WebP, máximo5MiB, verificações Cloudinary/pertencimento existentes. URL HTTPS continua disponível como alternativa discreta.
- Exemplares em seção separada, cartões responsivos com localização, aquisição e situação; edição de exemplar, histórico com vazio explícito, baixa/reativação e adicionar exemplar preservados. Desejados têm aquisição com local/data e eventuais exemplares anteriores preservados.
- Mover para desejados e exclusão em Mais ações. Regras de histórico e confirmações atuais permanecem. A aquisição conserva idempotência após perda da resposta.
- Voltar ao catálogo preserva busca, filtros, página, modo, densidade e posição. O botão Voltar funciona também ao abrir o livro diretamente. Compatibilidade com URLs antigas `?livro=`.

## Decisões de execução do agente

Sem novas dependências nem migração. Reutilizar PUT do livro com campo opcional `cover_public_id`: o servidor verifica a imagem, valida todos os campos e confirma tudo numa transação; URL manual diferente limpa o vínculo gerenciado antigo. Arquivos selecionados só são enviados ao salvar; upload concluído permanece reutilizável se o PUT precisar de retry. Não apagar imagens antigas nem arquivos abandonados nesta entrega.

Filtros/paginação ficam na query do catálogo, com estado/rolagem por histórico de navegação; dados bibliográficos e contatos não são salvos no armazenamento do navegador. Mudanças não salvas exigem confirmação ao navegar, fechar ou atualizar a aba. Cancelar é a ação explícita de descartar o rascunho e age imediatamente, conforme a prévia aprovada; não apresenta uma segunda confirmação. Erros persistem junto da tarefa, sucesso usa toast. Abrir outra rota de livro limpa os dados anteriores imediatamente. Não introduzir sinopse, leitura, avaliação ou novos campos bibliográficos nesta entrega.

## Prova e operação

TDD para atomicidade e isolamento da edição com capa; testes de rotas diretas/nova aba, campos completos, salvar/cancelar imagem e dados, retorno ao catálogo, exemplares/histórico e regressões de câmera/desejados. Revisão focada ao final. Actions continua desativado; publicação manual autorizada com testes locais, backup cifrado remoto e recuperação verificada antes de qualquer operação de produção.
