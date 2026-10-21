---
description: Acrescenta ao acervo as leis de um estado (e, se pedido, dos municípios dele)
argument-hint: UF [municipios]
allowed-tools: Bash
---
Argumentos: $ARGUMENTS

Rode `bash "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/acervo.sh" adicionar-estado <UF>` com a sigla informada. Se o usuário também pediu municípios, rode em seguida `acervo.sh adicionar-municipios <UF>`. Use segundo plano. Ao terminar, rode `acervo.sh status` e explique o resultado em linguagem simples, lembrando as lacunas daquele estado listadas em `~/leis-brasil-acervo/COBERTURA.md`.
