# Reprocessamento seguro de livros cadastrados

## Intenção

Preencher informações ausentes dos livros da biblioteca Julib, especialmente capa e número de páginas, sem alterar nenhum dado que já esteja preenchido.

## Objetivos e limites

- Processar somente livros da biblioteca indicada e que tenham ISBN válido para consulta por edição.
- Usar o enriquecimento existente por ISBN (Google Books, CBL, Mercado Editorial e Open Library), preservando seus limites e validação de imagens.
- Atualizar somente campos que estavam vazios antes da consulta e ainda estejam vazios no momento da gravação.
- Preservar todos os metadados, capa e identidade atuais (`source`/`source_id`), bem como exemplares, empréstimos e demais relações.
- Registrar proveniência apenas para os campos efetivamente preenchidos.
- Não criar livros, cópias, upload de capas ao Cloudinary, nem procurar correspondências aproximadas por título/autor.
- Ignorar livros sem ISBN ou sem resultado confiável. Sem garantia de correspondência de edição, não preencher por título/autor.

## Abordagens

1. **Comando dedicado com prévia padrão e aplicação explícita (recomendado):** chama o enriquecedor atual e usa atualizações condicionais para cada campo. A prévia não grava; `--apply` habilita gravações. Retomável, limitado à biblioteca, com limite de itens e intervalo configuráveis.
2. **Endpoint de reprocessamento em lote:** adiciona uma operação administrativa à API. Requer autenticação/autorização, controle de duração e estado de execução para não exceder o tempo das funções Vercel; custo e complexidade desnecessários para uma operação pontual.
3. **Reaproveitar o comando antigo de capas e complementar com Goodreads:** não cobre todas as APIs nem mantém proveniência de campo de forma consistente; o CSV Goodreads não é uma fonte geral para dados/capas.

A proposta é a abordagem 1, pois o processamento é pontual, controlável e pode ser executado localmente contra o banco remoto sem expor uma nova rota pública.

## Comportamento proposto

Criar `enrich_books` como comando Django. Sem `--apply`, consulta fontes e apresenta totais de livros elegíveis, campos que seriam preenchidos e casos sem resultado. Com `--apply`, grava apenas lacunas usando condições SQL que confirmem que cada campo continua vazio. A seleção considera livros com pelo menos um campo de enriquecimento ausente e ISBN válido; pagina em lotes e permite limitar/ajustar intervalo entre consultas. A execução pode ser repetida: campos já preenchidos deixam de ser elegíveis.

A atualização do mapa de proveniência deve mesclar apenas as origens correspondentes aos campos gravados, sem substituir origem de outros campos. Para capa, somente `cover_url` vazio e `cover_id` vazio são elegíveis. O número de páginas só é gravado quando ausente. Outros campos vazios poderão ser preenchidos pela mesma regra, se o enriquecedor retornar informação confiável.

## Verificação

Testes devem provar que a prévia não grava, `--apply` preenche lacunas e proveniência, valores existentes (incluindo capa manual e páginas) permanecem idênticos, ausência de ISBN/resultado é ignorada, repetição não altera registros e mudança concorrente entre consulta e gravação não é sobrescrita. O comando deve ser limitado à biblioteca solicitada.

## Decisões em aberto para implementação

Nenhuma: modo seguro padrão será prévia; gravação requer `--apply`; pesquisa sem ISBN ou por aproximação fica fora do escopo.
