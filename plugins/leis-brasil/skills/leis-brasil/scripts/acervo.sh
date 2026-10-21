#!/bin/bash
# Baixa, atualiza e amplia o acervo de leis (github.com/ctresb/leis).
# Uso: acervo.sh instalar | atualizar | adicionar-estado UF | adicionar-municipios UF | status
set -euo pipefail
ACERVO="${LEIS_BRASIL_ACERVO:-$HOME/leis-brasil-acervo}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
EXCLUIR=('!/**/_*')

pastas_atuais() { git -C "$ACERVO" sparse-checkout list | grep -v '^!'; }

aplicar() {
  git -C "$ACERVO" sparse-checkout set --no-cone "$@" "${EXCLUIR[@]}"
}

case "${1:-}" in
  instalar)
    if [ -d "$ACERVO/.git" ]; then echo "Acervo já instalado em $ACERVO"; exit 0; fi
    git clone --depth 1 --filter=blob:none --no-checkout --sparse https://github.com/ctresb/leis.git "$ACERVO"
    aplicar '/*.md' '/federal/' '/reguladores/' '/jurisprudencia/' '/tratados/'
    git -C "$ACERVO" checkout main
    echo ".indice-leis.tsv*" >> "$ACERVO/.git/info/exclude"
    python3 -I "$AQUI/leis.py" indexar ;;
  atualizar)
    git -C "$ACERVO" fetch --depth 1 origin main
    git -C "$ACERVO" reset --hard origin/main
    python3 -I "$AQUI/leis.py" indexar ;;
  adicionar-estado|adicionar-municipios)
    UF="$(echo "${2:?Informe a sigla do estado, ex.: GO}" | tr '[:lower:]' '[:upper:]')"
    [[ "$UF" =~ ^[A-Z]{2}$ ]] || { echo "Sigla inválida: $UF"; exit 1; }
    PASTA=$([ "$1" = adicionar-estado ] && echo "/estaduais/$UF/" || echo "/municipais/$UF/")
    ATUAIS=($(pastas_atuais))
    aplicar "${ATUAIS[@]}" "$PASTA"
    python3 -I "$AQUI/leis.py" indexar ;;
  status)
    echo "Acervo: $ACERVO"
    git -C "$ACERVO" log -1 --format='Última versão baixada: %cd' --date=format:'%d/%m/%Y %H:%M'
    echo "Pastas baixadas:"; pastas_atuais | sed 's/^/  /'
    echo "Normas no índice: $(($(wc -l < "$ACERVO/.indice-leis.tsv") - 1))"
    du -sh "$ACERVO" | awk '{print "Espaço ocupado: " $1}' ;;
  *) echo "Uso: $0 instalar | atualizar | adicionar-estado UF | adicionar-municipios UF | status"; exit 1 ;;
esac
