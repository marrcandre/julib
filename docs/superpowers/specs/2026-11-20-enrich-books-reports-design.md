# Relatórios do `enrich_books`

## Intenção

Permitir auditar por terminal e arquivo quais metadados foram encontrados, seriam preenchidos ou foram persistidos pelo comando `enrich_books`, sem depender de interface gráfica nem repetir consultas aos provedores.

## Objetivos

- Preservar prévia como padrão e o formato atual da saída de terminal/JSON resumido.
- Oferecer exportação detalhada opcional em CSV ou JSON, com modo explícito no relatório.
- Registrar por livro e campo estado, valor quando aplicável e provedor.
- Contar livros analisados, com novos metadados e sem novos dados, preenchimentos por campo e falhas por provedor.
- Em `--apply`, reportar como preenchido apenas o que `save_missing_fields` confirmou persistido após releitura sob lock.
- Manter consultas limitadas à biblioteca indicada e não incluir segredos nos relatórios.

## Não objetivos e restrições

- Sem interface gráfica, migration ou armazenamento de relatórios no banco.
- Sem requisições extras aos provedores para completar relatórios.
- Nenhum enriquecimento com gravação em banco de produção sem autorização específica.
- Compatibilidade com o uso atual de `--library`, `--limit`, `--delay` e `--apply`.

## Abordagens

1. **Flags explícitas para exportação (escolhida):** adicionar `--report-format csv|json` junto de `--report-file PATH`. Mantém a saída atual e evita arquivos inesperados.
2. **Exportação automática com nome convencionado:** menos flags, mas toda execução deixa arquivo e pode sobrescrever/confundir relatórios.
3. **Exportação isolada em subcomando:** separa responsabilidades artificialmente, pois exigiria executar o enriquecimento novamente ou armazenar resultados.

A primeira abordagem reutiliza os dados da única consulta já feita por livro e a confirmação de persistência existente. A escolha é uma decisão de implementação baseada na exigência de exportação opcional e no padrão de compatibilidade do comando.

## Contrato do relatório detalhado

Uma linha por livro e campo enriquecível: identificador, ISBN, título, campo, situação, valor e provedor. Situações exportadas: `já preenchido`, `seria preenchido`, `preenchido`, `não encontrado` e `erro`. Falhas HTTP/provedor e divergência de ISBN são representadas como `erro` nos campos ainda sem dados, com detalhe não sensível reservado ao agregado por provedor; valores existentes permanecem `já preenchido`. Valor é vazio quando não encontrado/erro. Na aplicação, campos candidatos que não persistiram após edição concorrente são `erro`, sem valor de candidato, e não incrementam preenchimentos.

O CSV usa cabeçalho estável; listas são codificadas como arrays JSON dentro da célula. JSON contém `mode`, `summary` e `details`. O stdout mantém o JSON agregado atual e ganha totais resumidos em texto.

## Arquivos

- `backend/library/management/commands/enrich_books.py`: construir resumo e detalhes a partir do resultado em memória, exportar CSV/JSON e distinguir prévia/aplicação.
- `backend/tests/test_book_metadata_enrichment.py`: cobrir exportações, ausência de resultados, HTTP 429, campos existentes e divergência entre prévia e aplicação.
- `docs/operations.md`: documentar comandos, modo, schema/colunas e interpretação.
