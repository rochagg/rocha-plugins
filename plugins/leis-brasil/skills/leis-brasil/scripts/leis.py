#!/usr/bin/env python3
"""Consulta à legislação brasileira em Markdown do repositório github.com/ctresb/leis, sem baixar o acervo.

Guarda no computador só o "sumário" do repositório (lista de arquivos, ~40 MB) e um índice compactado
de títulos e ementas (~30 MB). O texto de cada norma é baixado do GitHub na hora da consulta.

Uso:
  leis.py achar CTN                     acha uma norma por apelido
  leis.py achar --tipo "lei complementar" --numero 116 [--ano 2003] [--pasta reguladores/rfb]
  leis.py ementa credito insumo pis [--pasta reguladores/rfb] [--limite 30]
  leis.py listar estaduais/GO/leis-ordinarias/2020 [--filtro 21.000]   lista arquivos pelo nome
  leis.py artigo CTN 150                imprime o art. 150 (aceita "17-A" e --ate 155)
  leis.py baixar <apelido|caminho>      salva o texto integral numa pasta temporária e mostra o caminho
  leis.py info CTN                      cabeçalho (situação, fonte oficial)
  leis.py apelidos                      lista os apelidos conhecidos
Manutenção:
  leis.py instalar [--de-acervo PASTA]  baixa o sumário e monta o índice
  leis.py atualizar                     traz as novidades do repositório
  leis.py adicionar-estado UF [--municipios]
  leis.py status

Tudo fica em ~/leis-brasil (ou na variável LEIS_BRASIL_DIR).
"""
import argparse
import concurrent.futures
import csv
import gzip
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = os.path.expanduser(os.environ.get("LEIS_BRASIL_DIR", "~/leis-brasil"))
ARVORE = os.path.join(BASE, "arvore")
INDICE = os.path.join(BASE, "indice.tsv.gz")
PASTAS = os.path.join(BASE, "pastas-indexadas.txt")
CACHE = os.path.join(tempfile.gettempdir(), "leis-brasil-cache")
REPOSITORIO = "https://github.com/ctresb/leis.git"
RAW = "https://raw.githubusercontent.com/ctresb/leis/{versao}/{caminho}"
INDICE_PRONTO = os.environ.get("LEIS_BRASIL_INDICE_PRONTO", "https://github.com/rochagg/rocha-plugins/releases/latest/download")  # índice pré-montado
PASTAS_PADRAO = ["federal", "reguladores", "jurisprudencia", "tratados"]
CAMPOS = ["arquivo", "tipo", "numero", "data", "ano", "uf", "situacao", "revogada", "titulo", "ementa", "fonte", "resumo"]
TAMANHO_RESUMO = 400  # início do texto, para buscar por assunto quando a ementa não vem no cabeçalho
BYTES_INICIO = 8192  # o bastante para cabeçalho + resumo

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


# ---------- utilidades ----------

def sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def so_digitos(numero):
    return re.sub(r"\D", "", numero or "").lstrip("0")


def git(*args):
    # GIT_NO_LAZY_FETCH impede o git de baixar o conteúdo das leis por engano: aqui só usamos o sumário
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    r = subprocess.run(["git", "-C", ARVORE, *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} falhou: {r.stderr.strip()}")
    return r.stdout


def exigir_instalacao():
    if not os.path.isdir(ARVORE) or not os.path.exists(INDICE):
        sys.exit(f"Plugin não instalado em {BASE}. Rode: leis.py instalar  (ou /leis-brasil:instalar-acervo)")


def versao():
    return git("rev-parse", "HEAD").strip()


def ler_texto_cabecalho(texto, com_resumo=False):
    campos = {}
    linhas = texto.split("\n")
    if not linhas or linhas[0].strip() != "---":
        return campos
    fim = None
    for i, linha in enumerate(linhas[1:], 1):
        if linha.strip() == "---":
            fim = i
            break
        m = re.match(r"^(\w+):\s*(.*)$", linha)
        if m:
            valor = m.group(2).strip()
            if len(valor) >= 2 and valor[0] == valor[-1] == '"':
                valor = valor[1:-1].replace('\\"', '"')
            campos[m.group(1)] = valor
    if com_resumo and fim is not None:
        corpo = "\n".join(linhas[fim + 1:])[:TAMANHO_RESUMO * 3]
        corpo = re.sub(r"^#.*$", "", corpo, count=1, flags=re.M)
        campos["resumo"] = re.sub(r"[\s*_#>]+", " ", corpo).strip()[:TAMANHO_RESUMO]
    return campos


def linha_do_indice(caminho, campos):
    return [caminho] + [re.sub(r"\s+", " ", campos.get(k, "")) for k in CAMPOS[1:]]


# ---------- acesso ao GitHub ----------

def baixar_github(caminho, so_inicio=False, tentativas=4):
    url = RAW.format(versao=versao_cacheada(), caminho=urllib.parse.quote(caminho))
    pedido = urllib.request.Request(url, headers={"User-Agent": "leis-brasil-plugin"})
    if so_inicio:
        pedido.add_header("Range", f"bytes=0-{BYTES_INICIO - 1}")
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            erro = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            erro = e
        time.sleep(2 ** n)
    sys.exit(f"Não consegui baixar {caminho} do GitHub ({erro}). Verifique a internet.")


_VERSAO = None


def versao_cacheada():
    global _VERSAO
    if _VERSAO is None:
        _VERSAO = versao()
    return _VERSAO


def texto_completo(caminho):
    """Baixa (ou reaproveita do cache temporário) o texto integral de um arquivo do acervo."""
    local = os.path.join(CACHE, versao_cacheada()[:12], caminho)
    if not os.path.exists(local):
        texto = baixar_github(caminho)
        if texto is None:
            sys.exit(f"{caminho} não existe no repositório.")
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, "w", encoding="utf-8") as f:
            f.write(texto)
    with open(local, encoding="utf-8") as f:
        return local, f.read()


def indexar_remoto(caminhos):
    """Lê do GitHub só o começo de cada arquivo e devolve as linhas do índice."""
    caminhos = list(caminhos)
    linhas, feitos = [], 0

    def um(c):
        texto = baixar_github(c, so_inicio=True)
        campos = ler_texto_cabecalho(texto or "", com_resumo=True)
        return linha_do_indice(c, campos) if campos else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for linha in pool.map(um, caminhos):
            feitos += 1
            if linha:
                linhas.append(linha)
            if feitos % 2000 == 0:
                print(f"  {feitos}/{len(caminhos)} arquivos lidos", file=sys.stderr)
    return linhas


def arquivos_indexaveis(pastas, versao_git="HEAD"):
    if not pastas:
        return []
    saida = git("ls-tree", "-r", "--name-only", versao_git, "--", *pastas)
    return [c for c in saida.splitlines() if c.endswith(".md") and "/_" not in c and not c.startswith("_")]


# ---------- índice ----------

def ler_pastas():
    if not os.path.exists(PASTAS):
        return list(PASTAS_PADRAO)
    with open(PASTAS, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def gravar_pastas(pastas):
    with open(PASTAS, "w", encoding="utf-8") as f:
        f.write("\n".join(pastas) + "\n")


def carregar_indice():
    exigir_instalacao()
    csv.field_size_limit(10_000_000)
    with gzip.open(INDICE, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def gravar_indice(linhas):
    temporario = INDICE + ".tmp"
    with gzip.open(temporario, "wt", encoding="utf-8", newline="", compresslevel=6) as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(CAMPOS)
        w.writerows(linhas)
    os.replace(temporario, INDICE)


def linha_constituicao():
    return ["constituicao.md", "Constituição", "", "1988-10-05", "", "", "Em vigor", "false",
            "Constituição da República Federativa do Brasil de 1988", "Texto vigente (Planalto).",
            "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", ""]


def linhas_atuais(excluir=()):
    excluir = set(excluir)
    return [[l[k] for k in CAMPOS] for l in carregar_indice() if l["arquivo"] not in excluir]


# ---------- manutenção ----------

def instalar(args):
    os.makedirs(BASE, exist_ok=True)
    if not os.path.isdir(ARVORE):
        print("Baixando o sumário do repositório (só a lista de arquivos, sem o texto das leis)...")
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
                            REPOSITORIO, ARVORE])
        if r.returncode != 0:
            sys.exit("Falha ao baixar o sumário do repositório.")
    if os.path.exists(INDICE) and not args.refazer:
        print("Índice já existe. Use --refazer para montar de novo.")
        return
    pastas = ler_pastas()
    gravar_pastas(pastas)
    linhas = [linha_constituicao()]
    if args.de_acervo:
        # aproveita um acervo completo já baixado, sem nova ida ao GitHub
        origem = os.path.expanduser(args.de_acervo)
        for caminho in arquivos_indexaveis(pastas):
            local = os.path.join(origem, caminho)
            if os.path.exists(local):
                with open(local, encoding="utf-8", errors="replace") as f:
                    campos = ler_texto_cabecalho(f.read(BYTES_INICIO), com_resumo=True)
                if campos:
                    linhas.append(linha_do_indice(caminho, campos))
    elif baixar_indice_pronto():
        atualizar(args)
        return
    else:
        caminhos = arquivos_indexaveis(pastas)
        print(f"Montando o índice: lendo o começo de {len(caminhos)} arquivos no GitHub "
              "(demora; só precisa ser feito uma vez)...")
        linhas += indexar_remoto(caminhos)
    gravar_indice(linhas)
    print(f"Índice pronto: {len(linhas)} normas.")


def baixar_indice_pronto():
    """Baixa o índice publicado na release do plugin e alinha o sumário à versão do repositório usada nele."""
    print("Baixando o índice pronto (~30 MB)...")
    destino = {}
    try:
        for nome in ("indice.tsv.gz", "versao.txt"):
            pedido = urllib.request.Request(f"{INDICE_PRONTO}/{nome}", headers={"User-Agent": "leis-brasil-plugin"})
            with urllib.request.urlopen(pedido, timeout=120) as r:
                destino[nome] = r.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f"Índice pronto indisponível ({e}); vou montar o índice lendo o GitHub.")
        return False
    versao_indice = destino["versao.txt"].decode().strip()
    if subprocess.run(["git", "-C", ARVORE, "fetch", "-q", "--depth", "1", "origin", versao_indice]).returncode != 0:
        print("Não consegui alinhar o sumário ao índice; vou montar o índice lendo o GitHub.")
        return False
    git("update-ref", "HEAD", versao_indice)
    global _VERSAO
    _VERSAO = versao_indice
    with open(INDICE, "wb") as f:
        f.write(destino["indice.tsv.gz"])
    return True


def atualizar(_args):
    exigir_instalacao()
    antiga = versao()
    subprocess.run(["git", "-C", ARVORE, "fetch", "-q", "--depth", "1", "origin", "main"], check=True)
    nova = git("rev-parse", "FETCH_HEAD").strip()
    if nova == antiga:
        print("Já está na versão mais recente.")
        return
    mudancas = git("diff", "--no-renames", "--name-status", antiga, nova, "--", *ler_pastas()).splitlines()
    alterados = [l.split("\t", 1)[1] for l in mudancas if l]
    novos = [l.split("\t", 1)[1] for l in mudancas if l and l[0] in "AM"]
    git("update-ref", "HEAD", nova)
    global _VERSAO
    _VERSAO = nova
    novos = [c for c in novos if c.endswith(".md") and "/_" not in c]
    print(f"{len(alterados)} arquivos mudaram; lendo {len(novos)} novos/alterados...")
    linhas = linhas_atuais(excluir=alterados) + indexar_remoto(novos)
    gravar_indice(linhas)
    subprocess.run(["git", "-C", ARVORE, "gc", "-q", "--prune=now"], env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    print(f"Atualizado. Índice com {len(linhas)} normas.")


def adicionar_estado(args):
    exigir_instalacao()
    uf = args.uf.upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        sys.exit(f"Sigla inválida: {args.uf}")
    novas = [f"estaduais/{uf}"] + ([f"municipais/{uf}"] if args.municipios else [])
    pastas = ler_pastas()
    novas = [p for p in novas if p not in pastas]
    if not novas:
        print("Esse estado já está no índice.")
        return
    caminhos = arquivos_indexaveis(novas)
    print(f"Lendo o começo de {len(caminhos)} arquivos de {', '.join(novas)} no GitHub...")
    linhas = linhas_atuais() + indexar_remoto(caminhos)
    gravar_indice(linhas)
    gravar_pastas(pastas + novas)
    print(f"Pronto. Índice com {len(linhas)} normas.")


def status(_args):
    exigir_instalacao()
    print(f"Pasta: {BASE}")
    print("Versão do repositório: " + git("log", "-1", "--format=%cd", "--date=format:%d/%m/%Y %H:%M").strip())
    print("Pastas no índice: " + ", ".join(ler_pastas()))
    print(f"Normas no índice: {sum(1 for _ in carregar_indice())}")
    total = sum(os.path.getsize(os.path.join(r, a)) for r, _, fs in os.walk(BASE) for a in fs)
    print(f"Espaço ocupado: {total / 1024 / 1024:.0f} MB")


# ---------- consulta ----------

def no_sumario(caminho):
    return bool(git("ls-tree", "HEAD", "--", caminho).strip())


def resolver(alvo):
    """Converte apelido ou caminho em caminho do repositório."""
    chave = alvo.upper().replace(" ", "")
    if chave in APELIDOS:
        if APELIDOS[chave] is None:
            return "constituicao.md"
        tipo, numero, ano = APELIDOS[chave]
        for l in carregar_indice():
            if (l["tipo"] == tipo and so_digitos(l["numero"]) == numero
                    and (l["data"][:4] == ano or l["ano"] == ano) and not l["uf"]):
                return l["arquivo"]
        sys.exit(f"{alvo}: {tipo} {numero}/{ano} não está no índice.")
    exigir_instalacao()
    caminho = alvo.strip("/")
    if not no_sumario(caminho):
        sys.exit(f"Não encontrei '{alvo}'. Use um apelido (leis.py apelidos) ou o caminho que 'achar'/'listar' mostrou.")
    return caminho


def imprimir(linhas, limite):
    for i, l in enumerate(linhas):
        if i >= limite:
            print("... (mais resultados; aumente --limite)")
            break
        situacao = "REVOGADA" if l["revogada"] == "true" else (l["situacao"] or "situação não informada")
        uf = f" [{l['uf']}]" if l["uf"] else ""
        print(f"{l['arquivo']}\n  {l['titulo']}{uf} — {situacao}\n  {(l['ementa'] or l['resumo'])[:300]}")


def achar(args):
    if args.apelido:
        print(resolver(args.apelido))
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


def listar(args):
    exigir_instalacao()
    filtro = sem_acento(args.filtro) if args.filtro else None
    n = 0
    for c in git("ls-tree", "-r", "--name-only", "HEAD", "--", args.pasta.strip("/")).splitlines():
        if filtro and filtro not in sem_acento(c):
            continue
        if n >= args.limite:
            print("... (mais resultados; aumente --limite ou use --filtro)")
            break
        print(c)
        n += 1


def baixar(args):
    local, texto = texto_completo(resolver(args.alvo))
    print(f"{local}  ({len(texto) // 1024} KB) — leia ou pesquise neste arquivo com Read/Grep")


ART = re.compile(r"^[\s>*_#]*(?:~~)?[\s*_]*Art(?:igo)?\.?\s*(\d+)\s*(?:[º°o]|\.)?\s*(?:-\s*([A-Za-z]))?\b", re.I)
SECAO = re.compile(r"^(#+\s|(LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|DISPOSI[ÇC][ÕO]ES)\b)", re.I)


def chave_artigo(texto):
    m = re.match(r"^\s*(\d+)\s*(?:-\s*([A-Za-z]))?\s*$", texto)
    if not m:
        sys.exit(f"Número de artigo inválido: {texto}")
    return int(m.group(1)), (m.group(2) or "").upper()


def cabecalho_resumo(caminho, texto):
    c = ler_texto_cabecalho(texto)
    if not c:
        return f"[{caminho}] Constituição Federal de 1988 — texto vigente (Planalto)"
    situacao = "REVOGADA" if c.get("revogada") == "true" else c.get("situacao", "situação não informada")
    return (f"[{caminho}] {c.get('titulo', '')} — {situacao}; versão: {c.get('versao_texto', '?')}\n"
            f"Fonte oficial: {c.get('fonte', '?')}")


def artigo(args):
    caminho = resolver(args.alvo)
    _, texto = texto_completo(caminho)
    inicio, fim = chave_artigo(args.numero), chave_artigo(args.ate or args.numero)
    blocos, atual = [], None
    for linha in texto.splitlines():
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
    print(cabecalho_resumo(caminho, texto))
    if not blocos:
        print(f"\nArt. {args.numero} não encontrado neste arquivo (pode ter sido revogado, ou o OCR alterou a numeração). "
              "Use 'leis.py baixar' e pesquise o trecho no arquivo.")
        return
    for bloco in blocos:
        while bloco and (not bloco[-1].strip() or SECAO.match(bloco[-1].strip())):
            bloco.pop()
        print("\n" + "\n".join(bloco))
    if len({tuple(b[:1]) for b in blocos}) < len(blocos) or any("~~" in b[0] for b in blocos):
        print("\n[Atenção: há mais de uma redação deste artigo no arquivo; trechos entre ~~ ~~ são redações revogadas.]")


def info(args):
    caminho = resolver(args.alvo)
    print(cabecalho_resumo(caminho, baixar_github(caminho, so_inicio=True) or ""))


def apelidos(_args):
    for k, v in APELIDOS.items():
        print(f"{k:12} {'Constituição Federal de 1988' if v is None else f'{v[0]} {v[1]}/{v[2]}'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("instalar")
    s.add_argument("--de-acervo", help="pasta de um acervo completo já baixado, para montar o índice sem internet")
    s.add_argument("--refazer", action="store_true")
    s.set_defaults(f=instalar)
    sub.add_parser("atualizar").set_defaults(f=atualizar)
    s = sub.add_parser("adicionar-estado")
    s.add_argument("uf")
    s.add_argument("--municipios", action="store_true")
    s.set_defaults(f=adicionar_estado)
    sub.add_parser("status").set_defaults(f=status)
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
    s = sub.add_parser("listar")
    s.add_argument("pasta")
    s.add_argument("--filtro")
    s.add_argument("--limite", type=int, default=50)
    s.set_defaults(f=listar)
    s = sub.add_parser("baixar")
    s.add_argument("alvo")
    s.set_defaults(f=baixar)
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
