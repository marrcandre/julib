# Instruções para o Codex

## Fluxo de trabalho

- Trabalhe no diretório principal do repositório e em uma tarefa por vez.
- Não crie worktrees sem autorização explícita.
- Para cada tarefa, atualize a referência de `main` e crie uma branch convencional a partir dela. Prefira nomes descritivos no formato `codex/<nome-da-tarefa>`.
- Não implemente funcionalidades diretamente na `main`.
- Antes da integração, execute os testes pertinentes, revise o diff e valide o resultado.
- Integre à `main` somente após a validação.
- Após uma integração bem-sucedida, remova a branch de trabalho.

## Segurança e dados

- Não execute migrations em produção sem autorização explícita.
- Não publique em produção sem autorização explícita.
- Não modifique nem exclua dados de produção sem autorização explícita.
- Não execute operações destrutivas no Git sem aprovação explícita.
- Não inclua credenciais, dados privados ou backups no repositório.
- Preserve o isolamento entre bibliotecas e as regras de autorização existentes.
- Nunca use o banco de produção para testes.

## Organização e validação

- Evite branches abandonadas e mantenha a `main` limpa e sincronizada.
- Não crie branches ou worktrees desnecessárias.
- Prefira commits pequenos e descritivos.
- Não repita a suíte completa de testes quando resultados anteriores ainda forem válidos e nenhuma alteração relevante tiver ocorrido.
