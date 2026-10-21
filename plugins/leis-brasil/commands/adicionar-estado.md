---
description: Inclui na busca por assunto as leis de um estado (e, se pedido, dos municípios dele)
argument-hint: UF [municipios]
allowed-tools: Bash
---
Argumentos: $ARGUMENTS

Rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" adicionar-estado <UF>` com a sigla informada, acrescentando `--municipios` se o usuário também pediu os municípios. Use segundo plano: leva cerca de 1 minuto a cada 1.500 normas. Ao terminar, rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" status` e explique o resultado em linguagem simples. Mencione as lacunas daquele estado, que estão na tabela do arquivo COBERTURA.md do repositório (`python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" baixar COBERTURA.md`).
