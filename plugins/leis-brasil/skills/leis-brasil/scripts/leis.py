#!/usr/bin/env python3
"""Consulta ao acervo de legislação brasileira em Markdown (github.com/ctresb/leis).

Uso:
  leis.py indexar                       monta o índice (rode após baixar/atualizar)
  leis.py achar CTN                     acha uma norma por apelido
  leis.py achar --tipo "lei complementar" --numero 116 [--ano 2003] [--pasta reguladores/rfb]
  leis.py ementa "crédito presumido pis cofins" [--pasta reguladores/rfb] [--limite 30]
  leis.py artigo CTN 150                imprime o art. 150 (aceita "17-A" e --ate 155)
  leis.py artigo federal/leis-ordinarias/1996/lei-9430-1996-12-27.md 74
  leis.py info CTN                      cabeçalho (situação, fonte oficial)
  leis.py apelidos                      lista os apelidos conhecidos

O acervo fica em ~/leis-brasil-acervo (ou na variável LEIS_BRASIL_ACERVO).
"""
import argparse
import csv
import os
import re
import sys
import unicodedata

ACERVO = os.path.expanduser(os.environ.get("LEIS_BRASIL_ACERVO", "~/leis-brasil-acervo"))
INDICE = os.path.join(ACERVO, ".indice-leis.tsv")
CAMPOS = ["arquivo", "tipo", "numero", "data", "ano", "uf", "situacao", "revogada", "titulo", "ementa", "fonte", "resumo"]
TAMANHO_RESUMO = 600  # início do texto, para buscar por assunto quando a ementa não vem no cabeçalho

# apelido -> (tipo, numero, ano); "CF" é tratado à parte
APELIDOS = {
    "CF": None,
    "CTN": ("Lei Ordinária", "5172", "1966"),
    "CC": ("Lei Ordinária", "10406", "2002"),
    "CPC": ("Lei Ordinária", "13105", "2015"),
    "CDC": ("Lei Ordinária", "8078", "1990"),
    "CLT": ("Decreto-Lei", "5452", "1943"),
    "CP": ("Decreto-Lei", "2848", "1940"),
    "CPP": ("Decreto-Lei", "3689", "1941"),
    "LEF": ("Lei Ordinária", "6830", "1980"),
    "LINDB": ("Decreto-Lei", "4657", "1942"),
    "ECA": ("Lei Ordinária", "8069", "1990"),
    "LSA": ("Lei Ordinária", "6404", "1976"),
    "FALENCIAS": ("Lei Ordinária", "11101", "2005"),  # recuperação judicial e falência
    "LRF": ("Lei Complementar", "101", "2000"),  # responsabilidade fiscal
    "LPA": ("Lei Ordinária", "9784", "1999"),  # processo administrativo federal
    "PAF": ("Decreto", "70235", "1972"),  # processo administrativo fiscal
    "LGPD": ("Lei Ordinária", "13709", "2018"),
    "MS": ("Lei Ordinária", "12016", "2009"),  # mandado de segurança
    "LACP": ("Lei Ordinária", "7347", "1985"),
    "LIA": ("Lei Ordinária", "8429", "1992"),
    "JEC": ("Lei Ordinária", "9099", "1995"),
    "JEF": ("Lei Ordinária", "10259", "2001"),
    "LEI-KANDIR": ("Lei Complementar", "87", "1996"),
    "LC116": ("Lei Complementar", "116", "2003"),  # ISS
    "SIMPLES": ("Lei Complementar", "123", "2006"),
    "LC105": ("Lei Complementar", "105", "2001"),  # sigilo bancário
    "LC214": ("Lei Complementar", "214", "2025"),  # reforma tributária: IBS, CBS e IS
    "LEI9430": ("Lei Ordinária", "9430", "1996"),
    "LEI9249": ("Lei Ordinária", "9249", "1995"),
    "LEI8212": ("Lei Ordinária", "8212", "1991"),  # custeio da seguridade social
    "LEI8213": ("Lei Ordinária", "8213", "1991"),  # benefícios da previdência
    "LEI10637": ("Lei Ordinária", "10637", "2002"),  # PIS não cumulativo
    "LEI10833": ("Lei Ordinária", "10833", "2003"),  # Cofins não cumulativa
    "LEI7713": ("Lei Ordinária", "7713", "1988"),  # IRPF, isenções (art. 6º)
    "LEI8137": ("Lei Ordinária", "8137", "1990"),  # crimes contra a ordem tributária
    "LEI4320": ("Lei Ordinária", "4320", "1964"),
    "LEI8009": ("Lei Ordinária", "8009", "1990"),  # bem de família
    "LEI8245": ("Lei Ordinária", "8245", "1991"),  # locações
    "LEI8906": ("Lei Ordinária", "8906", "1994"),  # Estatuto da Advocacia
}


def sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def so_digitos(numero):
    return re.sub(r"\D", "", numero or "").lstrip("0")


def ler_cabecalho(caminho, com_resumo=False):
    campos = {}
    with open(caminho, encoding="utf-8", errors="replace") as f:
        if f.readline().strip() != "---":
            return campos
        for linha in f:
            if linha.strip() == "---":
                break
            m = re.match(r"^(\w+):\s*(.*)$", linha)
            if m:
                valor = m.group(2).strip()
                if len(valor) >= 2 and valor[0] == valor[-1] == '"':
                    valor = valor[1:-1].replace('\\"', '"')
                campos[m.group(1)] = valor
        if com_resumo:
            corpo = f.read(TAMANHO_RESUMO * 2)
            corpo = re.sub(r"^#.*$", "", corpo, count=1, flags=re.M)
            campos["resumo"] = re.sub(r"[\s*_#>]+", " ", corpo).strip()[:TAMANHO_RESUMO]
    return campos


def exigir_acervo():
    if not os.path.isdir(ACERVO):
        sys.exit(f"Acervo não encontrado em {ACERVO}. Rode /leis-brasil:instalar-acervo.")


def indexar(_args):
    exigir_acervo()
    total = 0
    temporario = INDICE + ".tmp"
    with open(temporario, "w", encoding="utf-8", newline="") as saida:
        w = csv.writer(saida, delimiter="\t", lineterminator="\n")
        w.writerow(CAMPOS)
        w.writerow(["constituicao.md", "Constituição", "", "1988-10-05", "", "", "Em vigor", "false",
                    "Constituição da República Federativa do Brasil de 1988", "Texto vigente (Planalto).",
                    "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", ""])
        for raiz, pastas, arquivos in os.walk(ACERVO):
            pastas[:] = sorted(p for p in pastas if not p.startswith((".", "_")) and p != "scripts")
            for nome in sorted(arquivos):
                if not nome.endswith(".md") or raiz == ACERVO:
                    continue
                caminho = os.path.join(raiz, nome)
                c = ler_cabecalho(caminho, com_resumo=True)
                if not c:
                    continue
                w.writerow([os.path.relpath(caminho, ACERVO)] + [
                    re.sub(r"\s+", " ", c.get(k, "")) for k in CAMPOS[1:]])
                total += 1
    os.replace(temporario, INDICE)
    print(f"Índice pronto: {total} normas em {INDICE}")


def carregar_indice():
    exigir_acervo()
    if not os.path.exists(INDICE):
        sys.exit("Índice ausente. Rode: leis.py indexar")
    csv.field_size_limit(10_000_000)
    with open(INDICE, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def resolver(alvo):
    """Converte apelido ou caminho em caminho absoluto de arquivo."""
    chave = alvo.upper().replace(" ", "")
    if chave in APELIDOS:
        if APELIDOS[chave] is None:
            return os.path.join(ACERVO, "constituicao.md")
        tipo, numero, ano = APELIDOS[chave]
        achados = [l for l in carregar_indice()
                   if l["tipo"] == tipo and so_digitos(l["numero"]) == numero
                   and (l["data"][:4] == ano or l["ano"] == ano) and not l["uf"]]
        if not achados:
            sys.exit(f"{alvo}: {tipo} {numero}/{ano} não está no acervo baixado.")
        return os.path.join(ACERVO, achados[0]["arquivo"])
    caminho = alvo if os.path.isabs(alvo) else os.path.join(ACERVO, alvo)
    if not os.path.exists(caminho):
        sys.exit(f"Não encontrei '{alvo}'. Use um apelido (leis.py apelidos) ou o caminho que 'achar' mostrou.")
    return caminho


def imprimir(linhas, limite):
    for i, l in enumerate(linhas):
        if i >= limite:
            print(f"... (mais resultados; aumente --limite)")
            break
        situacao = "REVOGADA" if l["revogada"] == "true" else (l["situacao"] or "situação não informada")
        uf = f" [{l['uf']}]" if l["uf"] else ""
        print(f"{l['arquivo']}\n  {l['titulo']}{uf} — {situacao}\n  {(l['ementa'] or l['resumo'])[:300]}")


def achar(args):
    if args.apelido:
        caminho = resolver(args.apelido)
        print(os.path.relpath(caminho, ACERVO))
        return
    tipo = sem_acento(args.tipo) if args.tipo else None
    numero = so_digitos(args.numero) if args.numero else None
    resultado = (l for l in carregar_indice()
                 if (not tipo or tipo in sem_acento(l["tipo"]))
                 and (not numero or so_digitos(l["numero"]) == numero)
                 and (not args.ano or l["data"][:4] == args.ano or l["ano"] == args.ano)
                 and (not args.pasta or l["arquivo"].startswith(args.pasta)))
    imprimir(resultado, args.limite)


def ementa(args):
    termos = sem_acento(" ".join(args.termos)).split()
    resultado = (l for l in carregar_indice()
                 if (not args.pasta or l["arquivo"].startswith(args.pasta))
                 and all(t in sem_acento(" ".join((l["titulo"], l["ementa"], l["resumo"]))) for t in termos))
    imprimir(resultado, args.limite)


ART = re.compile(r"^[\s>*_#]*(?:~~)?[\s*_]*Art(?:igo)?\.?\s*(\d+)\s*(?:[º°o]|\.)?\s*(?:-\s*([A-Za-z]))?\b", re.I)
SECAO = re.compile(r"^(#+\s|(LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|DISPOSI[ÇC][ÕO]ES)\b)", re.I)


def chave_artigo(texto):
    m = re.match(r"^\s*(\d+)\s*(?:-\s*([A-Za-z]))?\s*$", texto)
    if not m:
        sys.exit(f"Número de artigo inválido: {texto}")
    return int(m.group(1)), (m.group(2) or "").upper()


def cabecalho_resumo(caminho):
    c = ler_cabecalho(caminho)
    rel = os.path.relpath(caminho, ACERVO)
    if not c:
        return f"[{rel}] Constituição Federal de 1988 — texto vigente (Planalto)"
    situacao = "REVOGADA" if c.get("revogada") == "true" else c.get("situacao", "situação não informada")
    return (f"[{rel}] {c.get('titulo', '')} — {situacao}; versão: {c.get('versao_texto', '?')}\n"
            f"Fonte oficial: {c.get('fonte', '?')}")


def artigo(args):
    caminho = resolver(args.alvo)
    inicio, fim = chave_artigo(args.numero), chave_artigo(args.ate or args.numero)
    with open(caminho, encoding="utf-8", errors="replace") as f:
        linhas = f.read().splitlines()
    blocos, atual = [], None
    for linha in linhas:
        m = ART.match(linha)
        if m:
            if atual:
                blocos.append(atual)
            k = (int(m.group(1)), (m.group(2) or "").upper())
            atual = [linha] if inicio <= k <= fim else None
        elif atual is not None:
            atual.append(linha)
    if atual:
        blocos.append(atual)
    print(cabecalho_resumo(caminho))
    if not blocos:
        print(f"\nArt. {args.numero} não encontrado neste arquivo (pode ter sido revogado, ou o OCR alterou a numeração). "
              "Procure o trecho com busca de texto no arquivo.")
        return
    for bloco in blocos:
        while bloco and (not bloco[-1].strip() or SECAO.match(bloco[-1].strip())):
            bloco.pop()
        print("\n" + "\n".join(bloco))
    if len({tuple(b[:1]) for b in blocos}) < len(blocos) or any("~~" in b[0] for b in blocos):
        print("\n[Atenção: há mais de uma redação deste artigo no arquivo; trechos entre ~~ ~~ são redações revogadas.]")


def info(args):
    print(cabecalho_resumo(resolver(args.alvo)))


def apelidos(_args):
    for k, v in APELIDOS.items():
        print(f"{k:12} {'Constituição Federal de 1988' if v is None else f'{v[0]} {v[1]}/{v[2]}'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("indexar").set_defaults(f=indexar)
    a = sub.add_parser("achar")
    a.add_argument("apelido", nargs="?")
    a.add_argument("--tipo")
    a.add_argument("--numero")
    a.add_argument("--ano")
    a.add_argument("--pasta")
    a.add_argument("--limite", type=int, default=20)
    a.set_defaults(f=achar)
    e = sub.add_parser("ementa")
    e.add_argument("termos", nargs="+")
    e.add_argument("--pasta")
    e.add_argument("--limite", type=int, default=30)
    e.set_defaults(f=ementa)
    r = sub.add_parser("artigo")
    r.add_argument("alvo")
    r.add_argument("numero")
    r.add_argument("--ate")
    r.set_defaults(f=artigo)
    i = sub.add_parser("info")
    i.add_argument("alvo")
    i.set_defaults(f=info)
    sub.add_parser("apelidos").set_defaults(f=apelidos)
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
