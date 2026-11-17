# Importar uma coleção do Libib

A tela **Importar livros** oferece fluxos separados para Goodreads e Libib. O importador Libib aceita uma a cinco exportações CSV por sessão; o Libib exporta cada coleção em um arquivo separado. Confira cada prévia antes de confirmar: nenhum livro ou exemplar é criado no upload.

## Arquivo e limites

- CSV UTF-8, com ou sem BOM, lido com suporte a aspas, vírgulas internas e células multilinha.
- O conteúdo, e não a extensão ou o nome, identifica o formato. O cabeçalho precisa conter os campos de identificação e mapeamento do formato Libib, incluindo `item_type`, `title`, `creators`, `collection`, `ean_isbn13`, `upc_isbn10`, `tags`, `length` e `copies`.
- Até **5 MiB por arquivo**, **5 arquivos e 25 MiB no total por sessão**, **5.000 registros por arquivo** e **25.000 registros por sessão**.
- Até **100 exemplares por registro**. O valor `copies` deve ser inteiro positivo; vazio, zero, negativo, decimal ou excessivo torna a linha inválida.
- Cabeçalhos desconhecidos são reconhecidos e seus valores ficam disponíveis somente na sessão temporária.
- Um arquivo malformado, com codificação inválida, cabeçalho incorreto ou acima de 5 MiB aparece como erro individual; os demais arquivos válidos da mesma sessão continuam disponíveis para revisão e processamento.

## Mapeamento

| Libib | Julib |
|---|---|
| `title` | Título obrigatório, até 300 caracteres |
| `creators` | Autores; divide nomes separados por vírgula somente quando todas as partes parecem nomes completos. Vírgulas ambíguas ficam preservadas como um nome |
| `ean_isbn13` | ISBN-13 válido, com prioridade |
| `upc_isbn10` | Alternativa quando o ISBN-13 estiver ausente ou inválido; ISBN-10 válido é normalizado para ISBN-13 |
| `publisher` | Editora |
| `publish_date` | Ano de quatro dígitos; a prévia informa a perda de precisão |
| `length` | Número de páginas inteiro positivo; valor inválido é ignorado com aviso |
| `tags` | Tags separadas por vírgula; tags são reutilizadas ou criadas dentro da biblioteca atual |
| `copies` | Quantidade desejada de exemplares; cada exemplar é criado pelo serviço normal do Julib |
| `collection` | Metadado da origem mantido por linha; nunca vira uma localização Julib |
| `id` | Guardado temporariamente para revisão, mas não usado como chave de identidade |

Somente `item_type=book` pode ser importado. Outras mídias e linhas sem título ou criador aparecem como incompatíveis ou inválidas. UPCs genéricos não são aceitos como ISBN. Sem ISBN válido, o livro pode ser importado, mas não haverá correspondência automática por título.

Descrição, notas, preço, avaliações e resenhas, estado de leitura e datas pessoais, grupo e colunas personalizadas não são copiados para os modelos permanentes. A prévia lista os campos não importados que têm valores. Nenhum desses dados é escrito em `Book.provenance`.

## Correspondências e cópias

Uma correspondência automática exige ISBN normalizado dentro da biblioteca atual. Correspondências de título, autores, editora e ano aparecem apenas como possível duplicidade; não mesclam nem alteram livros automaticamente. Se o ISBN corresponder a um livro existente, a ação padrão não cria exemplares. Marque **Adicionar exemplares** para autorizar explicitamente a quantidade `copies`. Os metadados do livro existente nunca são sobrescritos.

O livro novo é criado uma vez, e os exemplares são numerados por `add_copy`, sob o lock da biblioteca. Tags, livro, exemplares e recibo são gravados na mesma transação por registro. Uma falha nessa transação não deixa recibo de conclusão.

## Idempotência e retomada

Cada arquivo temporário registra nome original, coleção, SHA-256 e estado. O recibo durável é escopado à biblioteca. Sua chave deriva do fingerprint dos campos da linha, sem o `id` Libib, e da ocorrência de linhas idênticas. Assim, o mesmo registro não acrescenta exemplares novamente se o arquivo for renomeado, se outra linha mudar ou se o Libib trocar o `id`. O SHA-256 completo do arquivo fica separado e permite identificar alterações. A constraint única no PostgreSQL e o lock da biblioteca protegem requisições concorrentes.

Um arquivo alterado tem outro hash e exige nova revisão. Registros alterados são comparados pelo ISBN dentro da biblioteca; exemplares só são acrescentados se o usuário selecionar essa ação. Sem ISBN, semelhanças bibliográficas são apenas sugestões e dependem da seleção explícita do usuário.

O cliente envia até 25 decisões por chamada e mostra os resultados por linha. Sessões, arquivos e linhas expiram após **sete dias**, conforme a limpeza existente; isso permite retomar o trabalho nesse período. Recibos de idempotência não dependem da sessão e não são removidos pela limpeza de sessões. Eles retêm somente hash, coleção, decisão, contagens e vínculos aos livros/exemplares, sem guardar novamente o CSV.

## Diferença do Goodreads

Goodreads continua usando o parser, as ações e as rotas já existentes: um exemplar por livro e correspondência por ISBN ou `source_id` Goodreads. Libib tem parser e processamento próprios, não usa `id` Libib como `source_id` e preserva a quantidade de `copies` com recibos entre sessões.

## Referências do formato

- A [documentação de exportação do Libib](https://support.libib.com/libib/website/settings.html) informa que a exportação CSV é feita por coleção, em arquivos separados.
- A [documentação de campos CSV do Libib](https://support.libib.com/libib/website/add-items.html) descreve `creators`, `copies`, ISBN-10/13 e tags separadas por vírgula.
- O arquivo de referência disponível no desenvolvimento contém o cabeçalho esperado e dois registros. Os valores reais não são reproduzidos aqui nem incluídos nos testes.
