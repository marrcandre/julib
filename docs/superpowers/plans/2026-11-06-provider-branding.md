# Fontes alternativas e crédito correto da capa

Decisão final do usuário em06/11/2026: manter GoogleBooks como alternativa, pesquisar outras fontes e priorizá-las. A opção anterior de desativar Google/remediar acervo foi revogada antes de qualquer alteração nos dados reais. Corrigir livro313 e remover créditos opcionais da interface. Não remover loginGoogle nem credenciais OAuth.

Evidência:313.source=openlibrary, capa gerenciada Cloudinary; apresentação confundia origem do cadastro com origem da capa. OpenLibraryCoversAPI trata link como cortesia. GoogleBooks exige crédito do conteúdo da API, incluindo metadados: mantê-lo claramente como Dados bibliográficos quando a capa é própria.

- [x] TDD: OpenLibrary preferida em busca e capas; Google como último fallback; BrasilAPI restrita a CBL/MercadoEditorial, sem seleção indireta Google. ISBN continua exato.
- [x] Separar metadata_attribution de cover_attribution sem migração; remover créditos opcionais, preservar fonte interna. Google deduplicado quando dados/capa usam o mesmo volume.
- [ ] Verificar70backend/14Vitest,22Playwright, revisão e backup cifrado restaurado. Publicar manualmente com Actions pausado e conferir313 por leitura.

Ordem: OpenLibrary → BrasilAPI com providers=cbl,mercado-editorial para ISBN → GoogleBooks. Para capas, OpenLibrary → GoogleBooks. Inventário da auditoria anterior (4cadastrosGoogle e21capasGoogle) é somente leitura; NÃO substituir/remover registros/capas ou inventar nova procedência. Capas Google existentes conservam crédito real; Google não é desativado.

Fontes consultadas: https://developers.google.com/books/branding ; https://openlibrary.org/dev/docs/api/covers ; https://openlibrary.org/developers/licensing ; https://brasilapi.com.br/docs . MercadoEditorial já é um provedor suportado pela BrasilAPI pública, sem adicionar conta ou plano. Inventaire foi identificado como possível API futura, sem integrar nesta correção para evitar dependência sem avaliação de cobertura/licença.

Segurança: testes usam chave fictícia da BooksAPI para impedir exposição de credenciais reais em tracebacks. Administração/rotação de credenciais é feita fora do código público; não alterar OAuth nem remover unilateralmente uma integração que o usuário decidiu manter.

Revisão focada identificou respostaOpenLibrarymalformada bloqueando fallback. Reproduzido RED com JSONnull/lista/docsinválido, corrigido no handler e confirmado GREEN. Verificação final74backend/14Vitest/22Playwright passou. Sem migrações nem reclassificação de registros. Backup cifrado remoto baixado e restaurado antes da publicação; nenhum achado importante pendente.
