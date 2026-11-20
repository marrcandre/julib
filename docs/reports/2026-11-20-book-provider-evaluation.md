# Avaliação exploratória dos provedores bibliográficos — 20/11/2026

## Objetivo e limite

Comparar cobertura por ISBN, correspondência de edição, subtítulo, descrição, assuntos, consistência e latência com uma amostra pequena. A avaliação usa consultas reais de leitura, não executa consultas em massa e não grava resultados no Julib. O escopo e a saída ficam limitados a metadados de catálogo e contagens; sinopses completas não são reproduzidas neste relatório.

Esta rodada não é suficiente para escolher uma ordem definitiva: BrasilAPI e Google Books responderam HTTP 429 em todas as consultas, e Google foi consultado sem chave. As respostas bloqueadas não são classificadas como falta de cobertura.

## Amostra e referências da edição

Três ISBNs brasileiros e três internacionais, de editoras, épocas e gêneros diferentes. Os dados de referência abaixo vêm das páginas das editoras e servem para detectar divergência de título, editora ou ano; não são fixtures nem respostas de provedores.

| Grupo | ISBN | Edição de referência |
|---|---|---|
| Brasil, ficção, reedição de clássico | `9788535914849` | *1984*, Companhia das Letras, 2009 ([editora](https://www.companhiadasletras.com.br/9788535914849-1984---traducao-de-alexandre-hubner-e-heloisa-jahn-3104/p)) |
| Brasil, não ficção/estudos literários | `9786557111185` | *Literatura infantil brasileira: História e histórias*, Editora Unesp, 2022 ([editora](https://editoraunesp.com.br/catalogo/9786557111185%2Cliteratura-infantil-brasileira)) |
| Brasil, literatura infantil | `9788510103886` | *O Saci*, Editora do Brasil, 2024 ([editora](https://editoradobrasil.com.br/o-saci/)) |
| Internacional, romance clássico | `9780141439518` | *Pride and Prejudice*, Penguin Classics, 2002 ([editora](https://www.penguinrandomhouse.com/books/286387/pride-and-prejudice-by-jane-austen-edited-with-an-introduction-and-notes-by-vivien-jones-original-penguin-classics-introduction-by-tony-tanner-cover-by-coralie-bickford-smith/9780141439518/)) |
| Internacional, romance clássico | `9780743273565` | *The Great Gatsby*, Scribner, 2004 ([editora](https://www.simonandschuster.com/books/The-Great-Gatsby/F-Scott-Fitzgerald/9780743273565)) |
| Internacional, romance clássico | `9780061120084` | *To Kill a Mockingbird*, Harper Perennial, 2006 ([catálogo de biblioteca](https://libkoha.alfaisal.edu/cgi-bin/koha/opac-ISBDdetail.pl?biblionumber=6706)) |

## Método reproduzível

Em 20/11/2026, consultei cada ISBN uma vez por adaptador, totalizando 24 requisições: seis para cada fonte. Nenhuma resposta foi repetida durante a rodada. Cada chamada recebeu timeout de cinco segundos e User-Agent com nome da aplicação. O User-Agent não incluiu e-mail/telefone de contato do Open Library; por isso, tratei as consultas dentro do limite padrão de 1 requisição/s e as espaçei em pelo menos 1,05 segundo. Não houve retry após erro.

- CBL: `https://brasilapi.com.br/api/isbn/v1/{isbn}?providers=cbl`
- Mercado Editorial: `https://brasilapi.com.br/api/isbn/v1/{isbn}?providers=mercado-editorial`
- Open Library: `https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=details&format=json`
- Google Books: `https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&maxResults=12`

Para repetir, consulte as seis linhas da tabela pelos quatro formatos acima, registre HTTP status e tempo monotônico de cada resposta, e compare ISBNs normalizados nos identificadores retornados. Uma correspondência de ISBN é condição para corresponder à edição; depois confronte título, editora e ano com a referência. Conte subtítulo não vazio, descrição em texto normalizado e assuntos distintos. Examine a descrição para relevância à obra, duplicações e texto de navegação; o comprimento sozinho não mede qualidade.

O recorte Open Library usou o endpoint Books legado com `jscmd=details`, assim como a implementação atual para validar edição. A própria documentação recomenda considerar Book Search API e diz que `jscmd=data` é um formato mais estável para os campos básicos. O resolvedor deve manter a verificação exata de ISBN qualquer que seja a API usada.

## Dados observados em chamadas reais

| Provedor consultado | HTTP 200 | HTTP 429 | Correspondência exata observada | Campos e consistência |
|---|---:|---:|---:|---|
| Open Library | 6/6 | 0/6 | 4/6 | Encontrou 1984, Pride and Prejudice, The Great Gatsby e To Kill a Mockingbird. Não encontrou título para os dois ISBNs brasileiros de 2022 e 2024. Subtítulo: 0/6; descrição: 3/6; assuntos: 1/6. |
| CBL via BrasilAPI | 0/6 | 6/6 | inconclusiva | Nenhum campo foi recebido. |
| Mercado Editorial via BrasilAPI | 0/6 | 6/6 | inconclusiva | Nenhum campo foi recebido. |
| Google Books | 0/6 | 6/6 | inconclusiva | Nenhum campo foi recebido; consulta feita sem chave de API. |

Nos quatro resultados Open Library com ISBN exato, três tinham um registro útil de edição. O quarto, *The Great Gatsby*, divergiu da referência: retornou editora `Independently Published` e ano 2021, enquanto a página da editora para esse ISBN identifica Scribner, 2004. Para *Pride and Prejudice*, título e ISBN coincidiram, mas Open Library retornou `Penguin Books`/2003 diante da referência `Penguin Classics`/2002; pode ser variação de catalogação, reimpressão ou erro e precisa de verificação bibliográfica antes de comparar campos como divergência definitiva.

Das três descrições Open Library não vazias, uma tinha 590 caracteres, uma 656 e uma apenas 27. A única lista de assuntos observada tinha seis itens. Não pontuei a qualidade textual das sinopses com um algoritmo: esta rodada mede presença e tamanho e registra inconsistência de edição, mas a avaliação semântica requer comparação humana com referências autorizadas.

Latência Open Library nesta amostra: mediana de aproximadamente 0,73 s por resposta (faixa 0,64–1,84 s). Os tempos das respostas 429 variaram de 0,35 a 1,33 s; não representam latência de serviço bem-sucedida nem permitem comparar provedores.

## Interpretação e limitações

- O Open Library ofereceu resposta consistente e correspondência exata para 4/6 nesta amostra, com cobertura observada melhor nos três ISBNs internacionais (3/3) do que nos brasileiros (1/3). A amostra é pequena e foi escolhida deliberadamente, portanto esses índices não estimam cobertura geral.
- A divergência de editora/ano no resultado do Great Gatsby mostra por que igualdade de ISBN e título deve prevalecer sobre abundância de metadados, mas ainda se deve verificar a consistência do próprio registro. Dados de ISBN corretos no registro não garantem que os outros campos estejam corretos.
- Os 429 de BrasilAPI e Google podem refletir bloqueio ou quota da rede de execução. Para Google, a documentação exige identificação por API key ou OAuth para dados públicos; sem chave, esta rodada não avalia o desempenho da configuração Julib com credencial.
- A documentação BrasilAPI expõe os quatro provedores de ISBN e descreve o serviço como experimental/solicita evitar abuso; não publica uma quota fixa que permita extrapolar esta rodada.
- Open Library solicita cache, User-Agent identificável e uso de baixo volume; a orientação atual publica 1 requisição/s para chamadas não identificadas e 3/s para identificadas. O serviço não é destinado a operar como backend de alto tráfego nem a coleta em lote.
- Os termos públicos da Livraria.ME/MercadoEditorial protegem seu conteúdo e restringem coleta automatizada e reprodução. Não encontrei nessa fonte uma licença explícita que resolva o uso da API de ISBN via BrasilAPI. Antes de ampliar a retenção ou distribuir descrições desse provedor, confirmar a autorização aplicável.
- Google Books restringe quotas por projeto e seus termos impõem condições para exibição e remoção de conteúdo. Manter atribuição e verificar os termos antes de uso comercial ou aumento de volume.
- Na implementação avaliada nesta rodada, a seleção era regional e repetia a ordem dentro de cada região. Essa estratégia foi posteriormente removida junto com a dependência do snapshot de ranges; a implementação atual usa uma prioridade global provisória declarada por campo.
- “Um adaptador por ISBN” não significa uma requisição HTTP: Open Library faz `data`, `details` e, quando necessário, uma requisição adicional à obra. A execução de `enrich_books` também aplica `--delay` entre livros, não entre essas chamadas internas.

## Recomendação histórica (supersedida)

**Nota de supersessão:** a recomendação abaixo foi registrada antes da remoção da classificação regional e permanece como histórico da avaliação, não como orientação operacional atual. A estratégia atual, definida sem nova investigação comparativa, é Open Library → Google Books → CBL → Mercado Editorial para todos os ISBNs, com listas declarativas independentes por campo. Essa prioridade é provisória. Os dados desta amostra favorecem Open Library somente neste recorte e são inconclusivos para os demais provedores; não demonstram que a ordem global seja superior.

Esta recomendação regional foi substituída sem nova investigação comparativa. A ordem regional permanece registrada aqui apenas como resultado histórico da avaliação.

## Estratégia operacional atual (provisória)

Open Library → Google Books → CBL → Mercado Editorial para todos os ISBNs, mantendo listas de prioridade independentes por campo. Essa ordem não decorre de comparação suficiente. A avaliação futura deve aguardar o cadastro e a importação dos livros pessoais completos; então poderá comparar cobertura, edição, idioma, completude, qualidade, capas, quotas e desempenho com provedores disponíveis e respeitando seus termos.

## Fontes oficiais consultadas

- [BrasilAPI — documentação dos endpoints](https://brasilapi.com.br/docs) e [aviso do projeto](https://brasilapi.com.br/).
- [CBL — Agência Brasileira do ISBN](https://cbl.org.br/plataforma_de_servic/isbn/).
- [Open Library — políticas de uso, taxa e cache](https://openlibrary.org/developers/api) e [Books API, incluindo aviso sobre o endpoint legado](https://openlibrary.org/dev/docs/api/books).
- [Google Books — uso da API e identificação de chamadas](https://developers.google.com/books/docs/v1/using), [termos do Books API](https://developers.google.com/books/terms) e [termos gerais das APIs](https://developers.google.com/terms/).
- [MercadoEditorial/Livraria.ME — termos públicos](https://livraria.mercadoeditorial.org/termos-de-uso).
