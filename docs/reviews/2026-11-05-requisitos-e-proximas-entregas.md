# Verificação dos requisitos do Julib — 05/11/2026

Base revisada: requisitos aprovados de 03/11, plano de 04/11, decisões posteriores da conversa, código atual da main e registros de validação. Estado do código da aplicação: 3ebae57; confirmação física do Poco F5 registrada em 79c4863. Esta auditoria documenta pendências e uma abordagem proposta; não inicia a implementação das próximas funcionalidades.

## Conclusão

O núcleo da primeira versão está entregue. Não faltam os módulos principais de catálogo, localização ou empréstimos. Existem lacunas específicas do desenho original, alguns refinamentos de gestão e validações operacionais ainda sem confirmação. As melhorias solicitadas depois da primeira versão, incluindo páginas, visualizações e câmera, já foram incorporadas.

## Requisitos atendidos

| Área | Evidência do que existe |
| --- | --- |
| Acesso | Google individual, allowlist, biblioteca compartilhada, autorização por biblioteca e ferramentas técnicas restritas a Marco. |
| Catálogo | Cadastro/edição manual, ISBN opcional e normalizado, dados externos editáveis, múltiplos exemplares, aquisição própria e número interno. |
| Busca/câmera | Título/autor/ISBN, consulta automática de ISBN lido, revisão antes de salvar, cadastro contínuo e alternativa manual. Usuário confirmou câmera e buscas no Poco F5. |
| Organização | Tags criáveis e associáveis aos livros; localização hierárquica, edição, ciclos bloqueados, filtro por descendentes/sem localização e movimentação em lote. |
| Circulação | Pessoas reutilizáveis, contatos obrigatórios/opcionais conforme decisão, três datas, mês calendário, devolução, atraso, perda, venda/doação, reativação e histórico por pessoa/exemplar. |
| Importação | Prévia Goodreads, seleção, cópia explícita, lotes de 25, retomada e idempotência. 312 livros e exemplares importados; páginas recuperadas para 284. |
| Apresentação | Painel, cinco últimas aquisições distintas por data, capas/cartões/lista, densidade de 3 a 10 por usuário, busca em 300 ms e limpeza; capas no editor/detalhes/empréstimos. |
| Imagens | Referências externas com atribuição; upload manual assinado e verificado no Cloudinary, com capa gerenciada no backup. |
| Compartilhamento | Link público somente leitura, revogável, sem locais, contatos, números de exemplares ou histórico. |
| Identidade/PWA | Menu superior, paleta aprovada, dois temas com preferência inicial do sistema, avatar Google, Sobre/homenagem/PIX, manifesto e ícones, aviso sem conexão. Instalação física ainda precisa de confirmação. |
| Engenharia/operação | Django/Ninja/uv/PostgreSQL e Vue/PrimeVue/TS; Admin/OpenAPI; monorepositório público MIT; CI/CD condicionado a testes e backup; banco local separado; cópias cifradas e recuperação já testada. |

## Pendências de implementação e abordagem

### 1. Importação: erros por linha e consulta de sessão expirada — prioridade alta

**Estado:** a prévia e o processamento existem. Porém, um erro de validação interrompe o lote no primeiro registro inválido. Não há erro persistido por linha e as próximas linhas não são processadas nessa chamada. A expiração já é validada no processamento e na listagem, mas não no GET direto de detalhes: sessão com oito dias ainda responde 200 enquanto não for removida pela rotina diária. O acesso continua restrito ao participante da mesma biblioteca.

**Abordagem:** primeiro aplicar a mesma regra de sete dias ao GET de detalhes. Depois, registrar estado/mensagem de erro por linha; processar cada linha em transação independente, mantendo o resultado das válidas; permitir corrigir/repetir apenas as falhas sem duplicar as concluídas. Erros de autorização e sessão inválida continuam interrompendo a requisição inteira. A interface mostra criados, existentes e falhas com sua linha e ação possível. Migração aditiva e contrato compatível com os lotes atuais.

**Aceite:** lote com inválida entre válidas conclui as válidas; falha aparece na linha correta; repetir não duplica; sessão expirada não pode ser consultada nem processada.

**Código:** backend/library/imports.py:67, backend/library/api.py:386 e frontend/src/pages/ImportBooks.vue.

### 2. Possível duplicata sem ISBN — prioridade alta

**Estado:** ISBN repetido já é impedido e a interface confirma adicionar outra cópia. Sem ISBN, título e autores iguais permitem novo cadastro sem aviso. O desenho original prevê sugestão de possível duplicado nesses casos.

**Abordagem:** consulta de possíveis correspondências na mesma biblioteca por título/autores normalizados. Apresentar candidatos com edição/idioma/quantidade de exemplares para escolher adicionar cópia ou manter uma edição separada. Não mesclar automaticamente e não transformar semelhança textual em unicidade rígida. Preservar a chave idempotente de cadastro.

**Aceite:** avisa antes de criar; permite duas edições legítimas; adicionar cópia usa a edição escolhida; nenhuma outra biblioteca aparece na sugestão.

**Código:** backend/library/services.py:52 e frontend/src/pages/Books.vue:267.

### 3. Correção de cadastro equivocado pela interface — prioridade média

**Estado:** baixa e reativação já existem. Há DELETE de livro somente sem exemplares, mas falta o fluxo de exclusão/correção na interface e não existe DELETE de exemplar. Dar baixa por venda/doação/perda não descreve corretamente um cadastro feito por engano.

**Abordagem proposta:** serviço compartilhado pela API/Admin que examine histórico e dependências e apresente o motivo de um bloqueio. Permitir exclusão somente para registros realmente elegíveis, com confirmação. Quando existirem referências técnicas de importação/idempotência, propor anulação lógica do cadastro equivocado, preservando essas referências; nunca apagar histórico de empréstimo para liberar a exclusão. A escolha da anulação é um detalhe novo a consolidar antes de implementar, não uma regra já aprovada.

**Aceite:** histórico preservado, contagens e catálogo público corretos, sem recriar exemplares ao repetir uma operação antiga.

**Código:** backend/library/api.py:171, backend/library/models.py (Registration/ImportRow) e ações dos exemplares em frontend/src/pages/Books.vue.

### 4. Gestão completa de tags na aplicação — prioridade média

**Estado:** criar tag, associar/desassociar de um livro e filtrar já funciona. Falta renomear/excluir a própria tag pela aplicação/API; renomear é possível no Admin. É um complemento ao gerenciamento atual, sem introduzir categorias hierárquicas.

**Abordagem:** painel simples de tags, renomeação com validação de conflitos e exclusão confirmada mostrando quantos livros serão afetados. Remover a associação sem apagar livros. Mesclar tags semelhantes seria outra função, não necessária nessa entrega.

**Aceite:** alteração aparece em todos os livros; exclusão não altera acervo/exemplares; isolamento entre bibliotecas e confirmação testados.

**Código:** backend/library/api.py (GET/POST /tags), frontend/src/pages/Books.vue e backend/library/admin.py.

### 5. Limpeza segura de capas órfãs — prioridade técnica média

**Estado:** não há rotina que encontre e limpe uploads abandonados ou capas antigas substituídas. O desenho prevê essa manutenção para reduzir consumo desnecessário. Os uploads e backups das capas atualmente referenciadas já funcionam.

**Abordagem:** inventário limitado ao prefixo julib/, comparação com todos os cover_id referenciados, carência para uploads recentes e prévia obrigatória antes da aplicação. Limitar quantidade por execução e registrar resultado sem imagens/dados pessoais. Validar com ativos sintéticos; jamais tocar nos ativos dos outros projetos da conta compartilhada. Só agendar depois de conferir as regras de preservação e a prévia.

**Aceite:** capa usada e upload recente preservados; órfão antigo identificado; prefixos alheios não são candidatos; falha interrompe a limpeza com relatório.

**Código:** backend/library/media.py e POST /books/{pk}/cover em backend/library/api.py; nenhum comando de limpeza de mídia foi encontrado.

## Complementos úteis, sem tratá-los como requisitos originais faltantes

- **Ordenação escolhida pelo usuário:** hoje o catálogo é ordenado por título no servidor. Acrescentar opções como aquisição/autor com lista permitida de ordenações e desempate estável; manter paginação e filtros no backend. O desenho pede ordenação no servidor, já existente, mas não define explicitamente esse seletor.
- **Paridade da coleção compartilhada:** a API pública aceita tag_id, mas sua interface só oferece busca por título. Expor filtro de tags, busca por autor/ISBN e os novos modos de visualização seria um refinamento, mantendo um contrato público próprio. Não foi prometida paridade completa com a tela privada.
- **Deduplicação do backup de mídia:** evolução condicionada ao volume. Hoje há snapshots completos com limite interno de 50 MiB e falha explícita ao exceder. Implementar armazenamento deduplicado/manifestos e provar restauração/rotação somente se o crescimento exigir. Não é bloqueio comprovado hoje nem autorização de custo adicional.
- **Cópia automática de capas externas para Cloudinary:** permanece sem execução conforme a decisão registrada após avaliar as fontes. O upload de imagens fornecidas pelo usuário já está ativo. Uma rotina de cópia futura precisa limitar-se às imagens/fontes com autorização de uso confirmada; não basta trocar a URL no banco.

## Validações e operação, sem confundir com funcionalidade faltante

- Login real da Juliana confirmado pelo usuário em 05/11/2026 no celular dela; pendência de autenticação encerrada. Uso dos demais fluxos de gestão com essa conta ainda não foi detalhado.
- Confirmar instalação e abertura do PWA, login e retorno ao app instalado no Poco F5 e Samsung A34. A câmera e as buscas no Poco F5 já foram confirmadas; login e câmera no Samsung A34 também foram confirmados pelo usuário em 05/11/2026. A instalação como PWA continua sem confirmação.
- Acrescentar jornada de execução de mutação pelo Swagger em navegador com sessão/CSRF; há testes de autorização, schema e operações da API, mas não uma jornada dessa interação completa.
- Confirmar segunda cópia segura da chave de recuperação e notificações de falha do Actions na conta do usuário. Não inferir configuração pessoal a partir dos workflows.
- Recuperação do banco e primitivas de recuperação da mídia já foram testadas. Um assistente automatizado de recuperação completa da conta Cloudinary não existe; o procedimento atual é documentado e manual, conforme operação.

## Evidência desta auditoria

Inspeção estática de modelos, API, services, Admin, páginas, manifesto, testes e workflows. Sondagens adicionais executadas somente no PostgreSQL local, com dados sintéticos e rollback da transação:

- Dois livros sem ISBN com o mesmo título/autor: ambos POST 200, sem aviso de duplicidade.
- Renomear/excluir tag pela API: 404; excluir exemplar: 405; excluir livro com exemplar: 400.
- Importação com primeira linha inválida: ambas as linhas ficam sem resultado e a válida seguinte não é criada.
- Sessão de importação com oito dias: GET direto 200; listagem já a oculta.

Workflow privado conferido por leitura no GitHub: agendamento diário UTC 06:23, retenção sete dias, cleanup_imports antes da cópia e backup com mídia. Última execução conferida 42035889419, concluída com sucesso em 05/11/2026. Código operacional fixado em 3161b64. CI integrado mais recente conferido: 42035538576, aprovado. Não foi reexecutada a suíte completa nesta auditoria, pois não houve alteração de código. Nenhuma alteração na aplicação ou nos dados de produção foi feita.

## Sequência de entrega recomendada

1. Corrigir expiração dos detalhes e erros por linha da importação.
2. Aviso de duplicata sem ISBN.
3. Gestão de tags e fluxo seguro para cadastro equivocado, em entregas separadas.
4. Inventário/limpeza de mídia com prévia e limites.
5. Complementos opcionais de catálogo/compartilhamento e escala de backup, conforme necessidade.

Executar cada entrega com teste que reproduza a lacuna, implementação mínima, atualização do contrato OpenAPI, testes de API/interface, CI e deploy. Usar migrações aditivas quando necessárias e o backup já integrado ao pipeline; manter a infraestrutura existente e o orçamento gratuito. As validações físicas e da segunda conta podem ocorrer em paralelo, sem desenvolver outro módulo.

Convites, cadastro aberto/outras bibliotecas, leitura/avaliações, notificações, reservas, categorias hierárquicas, etiquetas e uso offline continuam fora da primeira versão. A futura abertura exige um desenho próprio para participação/convites, remoção de acesso e escolha de biblioteca; não basta retirar a allowlist, pois o primeiro login hoje associa à biblioteca inicial.
