# Relatório: completude dos dados e capas das APIs

Data: 08/11/2026. Escopo solicitado: análise e proposta; nenhuma alteração de aplicação, banco ou publicação. Ajustes de edição/toasts/capa clicável continuam adiados.

## Conclusão

A alteração anterior priorizou fontes alternativas, mas deixou o fallback incompleto para o objetivo de obter dados e capa: a integração para na primeira resposta com algum resultado, independentemente de completude. Reordenar provedores sem corrigir esse critério não resolve o problema. Recomendo restaurar Google Books como primeira tentativa na busca geral e usar enriquecimento por dados faltantes, com BrasilAPI e Open Library como complementos efetivos. Nenhuma fonte garante capa de todas as edições.

## Evidência no código atual

- `backend/library/providers.py`: sequência Open Library → BrasilAPI (CBL/Mercado Editorial, somente ISBN) → Google Books. Retorno imediato se Open Library tiver qualquer candidato, inclusive sem capa; retorno imediato também após BrasilAPI.
- Open Library usa `/search.json` e extrai título/autores/`first_publish_year`/`cover_i`; não consulta a edição exata. Não aproveita editora, páginas ou idioma. O ano da primeira publicação da obra pode ser diferente do ano da edição do ISBN.
- BrasilAPI: o adaptador devolve `cover_url` vazio incondicionalmente. A CBL efetivamente retorna capa nula, mas Mercado Editorial pode devolver `cover_url`; essa informação é descartada pelo Julib. O campo `provider` também não é preservado, restando a origem genérica BrasilAPI.
- O agregador BrasilAPI usa `Promise.any` entre provedores: vence a primeira resposta bem-sucedida, não a mais completa. Passar `providers=cbl,mercado-editorial` não garante comparar as duas nem priorizar sua qualidade.
- `cover_lookup.py` é usado pelo comando `enrich_covers`, não pelo cadastro normal ou pela seleção de candidato. Portanto, localizar metadados não dispara automaticamente a recuperação de capa em outra API.
- O comando só trata registros com URL e identificador de capa vazios; uma URL existente porém quebrada não é considerada faltante.
- A busca normal aceita a URL anunciada sem verificar se a imagem existe. A rotina separada verifica HTTP/tipo de conteúdo, mas isso, isoladamente, pode aceitar imagens de substituição. Open Library oferece `default=false` para retornar 404 em vez de imagem vazia.
- `Books.vue` inclui `BookCredits` em cada item; `SourceAttribution.vue` atualmente mostra somente créditos Google. As referências opcionais Open Library/CBL já estão ocultas ali. Os detalhes também exibem os créditos Google.
- A origem da capa hoje é inferida pelo domínio da URL em `presentation.py`. Hospedagem e procedência precisam ser separadas para permitir cópia gerenciada sem perder a origem real.

## Verificação real em pequena amostra

Consultas públicas em 08/11/2026, com a chave privada atual para Google Books; sem consultar ou modificar o banco. Comparação normalizou ISBN-10/13 equivalentes. Esta amostra diagnostica a integração, não é um ranking estatístico de cobertura.

| ISBN | Google Books (consulta ISBN) | BrasilAPI CBL/ME | Open Library |
|---|---|---|---|
| 9788570550156 | Sem correspondência exata nesta consulta | CBL: A mensagem de 2 Timóteo; sem capa | Sem resultado nas consultas usadas |
| 9786583581112 | Sem correspondência exata nesta consulta | CBL: Solo, com editora/ano/páginas; sem capa | Sem resultado nas consultas usadas |
| 9788535914849 | 1984, sem referência de capa na resposta consultada | CBL: 1984, dados bibliográficos; sem capa | Search: Nineteen Eighty-Four; Books por ISBN: 1984, editora, 416 páginas e referência de capa |
| 9780261102217 | The Hobbit, com referência de capa | HTTP 400 nesta consulta | Edição encontrada, editora, 310 páginas e referência de capa |

As chamadas Google responderam HTTP 200 nesta verificação. Não há evidência aqui de chave inválida ou de quota impedindo essas quatro consultas. Referência de capa significa URL/campo anunciado pela API: não foi feita validação visual dos arquivos nem afirmada cobertura universal. A CBL devolveu o primeiro ISBN em formato ISBN-10 equivalente, aceito pela normalização já existente no aplicativo.

## Abordagem recomendada

### Descoberta e enriquecimento separados

1. Manter a leitura da câmera e a consulta digitada: ambas já fornecem corretamente o identificador ou termo para a busca.
2. Usar Google Books como primeira tentativa na busca geral de título/autor, preservando a ordem de seus próprios resultados e apresentação exigida. Consultar Open Library quando não houver correspondência adequada ou faltar informação relevante. BrasilAPI permanece voltada ao ISBN.
3. Para um ISBN confirmado/um candidato selecionado, verificar campos ausentes. Tentar Google Books, consultar CBL/Mercado Editorial pela BrasilAPI quando necessário e usar a edição específica da Open Library como complemento. Obter separadamente as respostas CBL e ME se for necessário comparar a completude, em vez de presumir que o agregador o faz.
4. Não considerar sucesso completo apenas porque há título e autor. Continuar quando faltar capa, editora, ano da edição, idioma ou páginas. Um timeout ou campo vazio de um provedor não deve impedir tentar os demais nem descartar dados já encontrados.
5. Capa segue uma decisão independente: aproveitar referência válida da fonte consultada; se ausente/inválida, tentar as demais fontes compatíveis com o mesmo ISBN/edição. Entre imagens correspondentes, preferir resolução e qualidade adequadas. Aproveitar tamanhos maiores do Google quando disponíveis e Covers API da Open Library por ISBN/edição.
6. Proteger correspondência: ISBN exato normalizado tem prioridade. Sem ISBN, título sozinho não basta; autores, idioma e edição precisam ser compatíveis. Conflitos entre campos devem ser preservados/apresentados, não resolvidos por mistura silenciosa. Não associar uma capa de outra edição apenas por ter o mesmo título.
7. Preservar respostas/procedência e preencher apenas campos ausentes no cadastro escolhido, respeitando condições das fontes. Não misturar ou reordenar indiscriminadamente resultados de busca Google com terceiros. Aplicar cache e tempo total limitado; não criar uma cascata sem limite de latência por candidato.
8. Cadastro continua possível quando nenhuma fonte tiver capa. Informar que a capa não foi encontrada; não prometer imagem para todo ISBN.

Google primeiro é uma recomendação inicial para busca geral, não uma alegação de que ele sempre tem dados/capa melhores. Os testes mostram por que CBL e Open Library precisam continuar participando mesmo com resultado do Google.

### Capas existentes e armazenamento

Corrigir o novo cadastro primeiro. Depois oferecer recuperação somente de capas ausentes/quebradas no acervo, com prévia/relatório e sem substituir imagens enviadas pelo usuário ou suas correções bibliográficas. Essa recuperação não foi executada nesta análise.

Encontrar a capa e copiá-la para Cloudinary são etapas distintas. O cadastro normal atualmente salva a URL recebida; enviar capa própria usa o fluxo Cloudinary. Uma eventual cópia gerenciada de capa externa precisa respeitar as condições da fonte e preservar sua procedência. Copiar uma imagem não transforma sua origem em conteúdo próprio nem elimina obrigações de atribuição.

### Origem somente nos detalhes

Concentrar informações detalhadas em uma seção “Fontes dos dados” nos detalhes: fonte do cadastro, fontes complementares por campo e origem da capa, separadas de sua hospedagem. Não inventar procedência mais específica para registros antigos quando ela não foi armazenada.

Podemos propor a remoção dos blocos textuais repetidos da grade. Há uma ressalva: Google exige atribuição junto ao conteúdo exibido e links apropriados. Um formato compacto deve ser validado contra essas regras; mover tudo para detalhes não é automaticamente suficiente. Se zero referências na lista for requisito absoluto, o conteúdo ali precisará vir de fontes que permitam esse formato. Não há proposta de desativar Google unilateralmente.

Open Library permite que o link de cortesia fique no detalhe, Sobre ou rodapé. Essa flexibilidade não deve ser extrapolada para todas as fontes. A indicação bibliográfica detalhada e os créditos obrigatórios são assuntos distintos.

## Plano de implementação sugerido, ainda não executado

- Adaptadores normalizados com aproveitamento de campos/capas já fornecidos, consulta por edição e identificação real do provedor.
- Orquestrador que continua por campos faltantes e trata falhas/tempo/cache sem regressão da identificação por ISBN/câmera.
- Proveniência explícita dos dados e da capa, compatível com os registros existentes. Escolher estrutura e eventual migração no desenho da implementação; hoje um único source/source_id não representa composição por campo.
- Detalhes com ficha de origem e grade mais limpa, preservando obrigações das fontes.
- Testes de: primeiro provedor sem capa e segundo com capa; CBL sem capa e ME com capa; conflito de edição; ISBN-10/13; fonte indisponível; imagem substituta/quebrada; capa própria preservada; origem correta após cópia no Cloudinary.
- Verificação com uma amostra maior de ISBNs reais antes de fechar prioridades e medir a melhoria de completude. Nenhum serviço pago ou nova credencial é necessário para começar a corrigir a integração existente; não foram contratadas novas fontes.

## Fontes primárias consultadas

- [Google Books: recursos e campos de volume](https://developers.google.com/books/docs/v1/reference/volumes)
- [Google Books: diretrizes de atribuição e resultados](https://developers.google.com/books/branding)
- [Open Library: Search API e distinção obra/edição](https://openlibrary.org/dev/docs/api/search)
- [Open Library: Books API e consulta ISBN/edição](https://openlibrary.org/dev/docs/api/books)
- [Open Library: Covers API, imagens vazias e link de cortesia](https://openlibrary.org/dev/docs/api/covers)
- [BrasilAPI: implementação do agregador ISBN](https://github.com/BrasilAPI/BrasilAPI/blob/main/pages/api/isbn/v1/%5Bisbn%5D.js)
- [BrasilAPI: retorno CBL](https://github.com/BrasilAPI/BrasilAPI/blob/main/services/isbn/cbl.js)
- [BrasilAPI: retorno Mercado Editorial](https://github.com/BrasilAPI/BrasilAPI/blob/main/services/isbn/mercadoEditorial.js)
