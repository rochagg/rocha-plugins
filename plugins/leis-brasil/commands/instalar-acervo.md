---
description: Prepara a consulta às leis brasileiras (baixa só o sumário do repositório ctresb/leis e monta o índice)
allowed-tools: Bash
---
Rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" instalar` em segundo plano. Sem um índice pronto, ele lê o começo de ~400 mil arquivos no GitHub e pode levar horas; se houver um acervo completo baixado em alguma pasta, use `--de-acervo <pasta>` para ser rápido. Ao terminar, rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" status` e explique ao usuário, em linguagem simples, o que foi instalado e quanto espaço ocupa.
