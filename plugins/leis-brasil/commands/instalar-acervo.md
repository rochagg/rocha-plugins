---
description: Prepara a consulta às leis brasileiras (baixa só o sumário do repositório ctresb/leis e monta o índice)
allowed-tools: Bash
---
Rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" instalar` em segundo plano. Normalmente ele baixa um índice pronto (~30 MB) publicado no GitHub e termina em menos de um minuto; só se esse download falhar ele monta o índice lendo ~400 mil arquivos, o que leva horas. Ao terminar, rode `python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/leis-brasil/scripts/leis.py" status` e explique ao usuário, em linguagem simples, o que foi instalado e quanto espaço ocupa.
