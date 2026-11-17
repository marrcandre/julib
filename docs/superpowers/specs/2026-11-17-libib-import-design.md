# Importação Libib — desenho técnico

## Intenção

Permitir importar uma ou várias bibliotecas exportadas pelo Libib em CSV, revisar os registros antes de criar dados e preservar quantidades de exemplares. O fluxo Goodreads continua compatível e independente.

## Objetivos e limites

- Aceitar CSV UTF-8 com/sem BOM; até 5 MiB por arquivo, 5 arquivos por sessão e 5.000 linhas por arquivo (25.000 por sessão). Falhas de leitura são registradas por arquivo e não bloqueiam os arquivos válidos da sessão.
- Suportar somente `item_type=book`; mostrar linhas incompatíveis e erros na prévia.
- Mapear título, `creators`, ISBN válido, editora, ano, páginas, tags, coleção e exemplares conforme a solicitação.
- Nunca corresponder automaticamente por título nem usar `id` Libib como identidade estável.
- Exigir seleção e confirmação antes de criar livros ou exemplares; permitir ignorar ou adicionar exemplares explicitamente a livro já encontrado por ISBN.
- Proteger reimportações entre sessões com recibos duráveis independentes da limpeza das sessões após sete dias.
- Preservar isolamento por biblioteca e usar os serviços existentes de criação de livros, tags e exemplares.
- Não importar campos sem destino; avisar quais foram ignorados. Manter os dados de origem na sessão temporária, sujeita à expiração atual.

## Abordagens

1. **Tabelas específicas ligadas à sessão e linhas (escolhida):** `ImportFile` registra cada CSV e `ImportReceipt` registra a conclusão por biblioteca e registro de origem. Constraints tornam identidade e isolamento explícitos; os recibos sobrevivem à expiração da sessão.
2. **Metadados JSON na sessão/linhas:** menos tabelas, porém integridade de identidade e unicidade depende da aplicação e é difícil de consultar/validar no PostgreSQL.

A abordagem 1 foi escolhida pelo usuário, priorizando integridade e idempotência. O parser Libib e as decisões de processamento serão funções separadas; o parser Goodreads e seus contratos permanecem intactos.

## Arquitetura e dados

- Adicionar `ImportSession.source` com default Goodreads e relação opcional da linha a `ImportFile`; as linhas existentes continuam sem arquivo.
- `ImportFile`: sessão, índice, nome fornecido pelo navegador, coleção, SHA-256, estado e contagens; unicidade `(session, position)`. Arquivos repetidos numa sessão são registrados com erro pelo parser.
- Guardar em cada `ImportRow.data` os campos normalizados, alertas, dados brutos necessários à revisão (não logs), índice da linha do arquivo e chave de registro determinística derivada do fingerprint dos campos da linha (sem `id`) e do número de ocorrência de linhas idênticas. O hash integral do arquivo é armazenado separadamente para detectar alterações.
- `ImportReceipt`: biblioteca, chave de origem SHA-256, hash do arquivo, coleção, fingerprint do registro, quantidade desejada/adicionada, decisão, estado, livro, exemplares criados e timestamps. Unicidade `(library, source_key)`, FKs compostas para livro/exemplares; recibos concluídos persistem após a sessão.
- Em conteúdo de linha idêntico, a mesma chave de origem bloqueia acréscimo de exemplares mesmo se o nome, o hash do arquivo ou o `id` Libib mudar. Se o arquivo mudou, o hash da sessão identifica a alteração; linhas alteradas exigem revisão e uma correspondência ISBN existente exige a escolha explícita “adicionar exemplares”.
- Uma transação por linha bloqueia a biblioteca, a linha e a chave do recibo; criação do livro, tags, N exemplares, recibo e resultado da linha são atômicos. Reutilizar `create_book`, `add_copy`, `owned`, `normalize_isbn`.
- Recebimentos importados como cópia vinculam recibo a todas as cópias via tabela associativa com constraints da biblioteca; `ImportRow.copy` existente continua representando no máximo uma cópia Goodreads.

## Interface e API

- Manter `/imports` existente para Goodreads; adicionar rotas Libib identificadas pelo campo `source`, sem mudar payloads Goodreads. Upload em lote usa multipart com até cinco arquivos e retorna uma sessão consolidada.
- Detalhes incluem arquivos, coleção, avisos, estado de cada linha e correspondência ISBN limitada à biblioteca.
- Processamento em lotes de até 25 decisões; resultado por linha, retomada e progresso do cliente refletem respostas reais.
- A tela suporta upload múltiplo, resumo consolidado, estados válidos/inválidos/incompatíveis, avisos de ISBN/data/campos ignorados, tags, coleção, cópias, decisão para livro existente, resultado e retomada.

## Segurança, retenção e validação

- Limites do servidor antes e durante leitura; `csv.DictReader` em modo estrito, decodificação UTF-8 estrita, validação de cabeçalho por campos obrigatórios, mensagens sem exceções internas.
- Recibos persistem; sessões, arquivos e linhas são eliminados pela rotina de limpeza após sete dias. O arquivo original não é retido; seus dados necessários à prévia ficam nas linhas temporárias.
- Testes cobrem parser, mapeamento, ações, cópias, transações, idempotência por conteúdo em sessões distintas, concorrência e isolamento. Validar migrations em PostgreSQL descartável se houver serviço configurado; nunca conectar a produção.
- Documentar o esquema conhecido, limites, comportamento e a disponibilidade estrutural do CSV de referência (dois registros; valores reais não são publicados).

## Decisões deixadas à implementação

- Estratégia de parsing de `creators`: usar vírgula como separador somente quando todas as partes resultantes parecem nomes completos; caso contrário preservar o valor como um único nome para não corromper nomes com vírgulas.
- Datas: extrair primeiro ano de quatro dígitos em data reconhecida; inválido vira vazio e aviso.
- ISBN-13 válido tem prioridade; fallback para ISBN-10 passa por `normalize_isbn`; ISBN inválido não bloqueia livro.
- `copies` deve ser inteiro positivo até 100; vazio ou inválido exige correção/seleção desabilitada e não é convertido silenciosamente.
- Tags separadas por vírgula conforme a documentação de CSV do Libib; remover vazias e limitar comprimento do modelo.
