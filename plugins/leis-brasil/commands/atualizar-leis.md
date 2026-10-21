---
description: Atualiza o índice de leis com as novidades do repositório ctresb/leis
allowed-tools: Bash
---
Rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" atualizar` em segundo plano. Ao terminar, rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" status` e informe ao usuário a data da versão e o total de normas no índice.
