# Contribuindo com o Julib

Leia o README e o desenho em docs/superpowers/specs. Abra uma issue para mudanças de escopo.

Use uma branch por mudança, teste que reproduza o comportamento antes de implementar e commits pequenos. Execute `make check` e a jornada `make e2e` com banco descartável antes de abrir PR. Nunca envie dados reais, credenciais, dumps ou imagens da biblioteca. Os testes usam contas fictícias e provedores simulados.

Preserve o isolamento por biblioteca, os schemas públicos explícitos, as regras compartilhadas entre Admin/API e a paleta/tema definidos. Atualize documentação e migrações quando necessário.
