# Fontes de livros, capas e atribuição — 06/11/2026

Decisão final do usuário: priorizar alternativas e manter GoogleBooks como fallback. Corrigir a atribuição indevida do livro313 após envio de capa própria. Não remover loginGoogle, não reescrever o acervo existente e não contratar serviços pagos.

| Fonte | Aplicação nesta entrega | Observações verificadas |
|---|---|---|
| OpenLibrary | Primeira busca por ISBN/título/autor e primeira busca de capa | Exigir ISBN equivalente nas buscas por código. A documentação de capas descreve link de cortesia como apreciado, inclusive no Sobre; não exige badge por livro. |
| BrasilAPI: CBL e MercadoEditorial | Segunda busca por ISBN, com provedores explícitos cbl,mercado-editorial | São provedores documentados da API pública. Retorna metadados; pode não oferecer capa. Não deixar o agregador escolher Google implicitamente. |
| GoogleBooks | Última busca quando as anteriores não retornam resultado; última tentativa de capa | Regras exigem atribuição do conteúdo obtido pela API. Mostrar apenas créditos necessários e distinguir dados bibliográficos da imagem atual. |
| Inventaire | Candidato pesquisado para avaliação futura | Documenta entidades por ISBN e outros identificadores. Não integrar sem avaliar cobertura das edições brasileiras, requisitos e regras das imagens. |

Não confundir licença do código de uma API com direitos sobre seu conteúdo ou imagens. Não copiar capas Google para Cloudinary para ocultar procedência. Fotos próprias enviadas pelo usuário são independentes dos metadados importados. Origem e identificador dos dados continuam armazenados internamente.

Implementação: cover_attribution passa a examinar a URL da imagem atual; metadata_attribution identifica os dados Google quando presentes. Dados API/OpenAPI geram campos separados, sem migração. Créditos iguais do mesmo volume são deduplicados; um volume diferente mantém seu próprio link. OpenLibrary/CBL não geram marcas visíveis opcionais na interface.

Fontes oficiais:
- https://openlibrary.org/developers/api
- https://openlibrary.org/dev/docs/api/covers
- https://openlibrary.org/developers/licensing
- https://brasilapi.com.br/docs
- https://developers.google.com/books/branding
- https://api.inventaire.io/
