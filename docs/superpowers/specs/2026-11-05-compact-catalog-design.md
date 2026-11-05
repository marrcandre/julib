# Catálogo compacto — desenho aprovado

Usuário aprovou a prévia navegável em 05/11/2026 e autorizou implementar com ajustes de densidade por dispositivo, slider e badge numérico. Referência local: .superpowers/brainstorm/348001-1793898416/content/catalog-layout-v1.html.

Intenção: priorizar busca e livros nas telas de celular e desktop. Remover frase decorativa; título compacto com badge numérico acessível. Cabeçalho global de uma linha, navegação em drawer no celular e links no desktop. O botão + abre câmera, busca externa ou cadastro manual. Menu secundário agrupa importação, organização e compartilhamento. Filtros em painel com rascunho/Aplicar/Limpar, contador e chips; visualização em painel com modos e slider inteiro de 3 a 10. Confirmações transitórias, erros persistentes.

Abordagens discutidas: cabeçalho compacto com navegação recolhida no celular (escolhido); lateral aberta no desktop reduziria espaço para capas. + no canto foi escolhido em vez de flutuante para não encobrir livros. A prévia foi avaliada antes desta autorização.

Densidade será guardada localmente por identificador do usuário, separada em cada navegador/dispositivo. Padrão inicial: quatro no celular e sete no desktop; escolha vale ao redimensionar o mesmo navegador. Não usar fingerprint nem sincronizar densidade entre aparelhos. Isso é uma escolha técnica explicitada na implementação. Modo capas/cartões/lista continua na conta; API anterior de preferências mantém compatibilidade, mas slider não altera sua densidade global legada.

Compartilhamento abre diálogo e consulta somente o estado ativo, nunca gera/revoga link ao abrir. Geração/renovação e desativação explícitas com confirmação; copiar link apenas após ação do usuário. Token existente não é recuperável do digest; novo token só é exibido na sessão em que foi gerado.

Invariantes: preservar câmera contínua/ISBN, cadastro idempotente, filtros no servidor, busca em 300 ms/respostas antigas descartadas, atribuição das fontes e dados privados. Nenhuma ação fictícia da prévia será transferida. Sem nova infraestrutura, migração de banco ou custo.

Aceite: primeira capa antes de 250 CSS px em 393×852 sem filtros; uma linha no header; ausência de overflow; controles secundários acessíveis por teclado, fechamento/foco e nomes; slider 3/10, persistência por usuário e independência entre contextos de navegador; fluxos reais de cadastro e câmera mantidos; consultar compartilhamento não modifica seu token; CI/deploy aprovados.
