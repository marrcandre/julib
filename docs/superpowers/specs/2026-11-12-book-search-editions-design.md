# Busca por edições e complemento bibliográfico

## Objetivo

Melhorar a busca por título para permitir identificar a edição antes de preencher ISBN, páginas, editora, ano e idioma. Extrair edição e idioma quando a fonte fornecer esses dados explicitamente. Preservar os dados já preenchidos.

## Abordagens

1. Recomendada: apresentar candidatos de edições específicas, com ISBN e informações editoriais, para escolha do usuário. Complementar apenas a edição selecionada. Evita atribuir páginas ou ano de uma edição diferente.
2. Escolher automaticamente uma edição de cada obra: exige menos interação, mas pode selecionar tradução, editora ou formato incorretos. Não recomendada.

## Comportamento proposto

- Buscar candidatos nas duas fontes de descoberta (Open Library e Google), em vez de ignorar Google quando houver resultados da Open Library.
- Usar dados de edições específicas da Open Library; não combinar listas agregadas de ISBN, editoras, anos e páginas de uma obra como se fossem de uma edição.
- Exibir ISBN, editora, ano, idioma e edição disponíveis em cada candidato. Candidatos sem ISBN continuam utilizáveis para cadastro manual, com indicação de que os dados estão incompletos.
- Ao selecionar uma edição com ISBN válido, manter o complemento atual por ISBN para preencher apenas os campos vazios, incluindo páginas.
- Obter edition_name e languages dos dados da edição na Open Library, sem inferir número de edição a partir do ano ou título. Não inventar idioma ou edição quando a fonte não fornecer.
- Incluir edição no critério de completude, mantendo o orçamento de 18 segundos, limites de respostas e cache existentes. Limitar a quantidade de consultas de descoberta e de candidatos para evitar buscar todos os detalhes de todas as edições.
- Deduplicar candidatos com o mesmo ISBN normalizado e manter edições com ISBN diferentes separadas.
- Preservar a origem dos campos e os valores existentes; nenhuma atualização em massa do acervo nesta mudança.
- Continuar funcionando com resultados parciais quando uma fonte falhar.

## Escopo e validação

Alterações nos adaptadores de busca, testes de enriquecimento e lista de candidatos no frontend. Sem mudança de esquema do banco. Testar separação entre edições, ISBN inválido/ausente, fontes indisponíveis, ausência de idioma/edição, preenchimento e preservação de páginas, proveniência e renderização das informações editoriais. Rodar testes e build localmente. Não publicar.
