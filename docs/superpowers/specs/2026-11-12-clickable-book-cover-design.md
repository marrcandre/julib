# Troca de capa pela imagem na edição de livros

## Objetivo

Permitir escolher uma nova capa clicando na imagem na tela de edição, deixando a ação visível com um ícone de lápis. Manter o botão “Trocar capa”, conforme escolha do usuário.

## Abordagens

- Capa clicável com lápis e botão “Trocar capa”: escolhida; oferece o atalho visual e conserva a ação escrita existente.
- Capa clicável com lápis, removendo o botão: reduz os controles, mas foi descartada por enquanto pelo usuário.

## Comportamento

- Toda a área da capa será um botão acessível por mouse, toque e teclado, com nome “Trocar capa”.
- Um lápis com fundo sólido ficará sempre visível no canto inferior direito. Hover e foco terão destaque e indicação da ação.
- O mesmo controle funcionará na área “Sem capa”.
- Clicar abrirá o seletor de arquivos já utilizado pelo botão existente.
- Durante o envio e salvamento, o controle ficará desabilitado como os demais campos.
- A seleção continuará mostrando uma prévia local, com opção de desfazer; o envio ocorrerá apenas ao salvar.
- Permanecem os formatos JPG, PNG e WebP e o limite de 5 MB.

## Escopo e implementação

Reaproveitar o fluxo de BookEditor.vue e os estilos existentes. Não alterar o backend nem acrescentar recorte, edição da imagem ou salvamento automático. Os detalhes de tamanho e contraste do indicador seguirão o estilo atual da aplicação.

## Validação local

Verificar abertura do seletor por clique e teclado, presença do lápis com e sem capa, prévia, desfazer, cancelamento e salvamento. Conferir a apresentação em desktop e celular e executar os testes relevantes de edição de livros.

Publicação fica para depois da validação local e aprovação do usuário.
