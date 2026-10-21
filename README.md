# rocha-plugins

Plugins do Claude Code para o escritório Rocha Advocacia.

## leis-brasil

Consulta o texto literal da legislação brasileira no repositório público
[ctresb/leis](https://github.com/ctresb/leis): Constituição, leis federais, atos da Receita Federal e do
CARF, súmulas e temas do STF/STJ/TST, tratados de bitributação e leis estaduais e municipais.
As leis não ficam no computador: o plugin guarda só um sumário e um índice (~70 MB) e baixa
cada texto do GitHub na hora da consulta.

### Instalar em um computador novo

Pré-requisitos: Claude Code, Python 3, git e o GitHub CLI logado na conta dona deste repositório
(`gh auth login` e depois `gh auth setup-git`, porque o repositório é privado).

```bash
claude plugin marketplace add rochagg/rocha-plugins
```

```bash
claude plugin install leis-brasil@rocha-plugins
```

Reinicie o Claude Code e rode `/leis-brasil:instalar-acervo`. Ele baixa um índice pronto (~30 MB) publicado nas releases deste repositório e termina em menos de um minuto.

### Atualizar o plugin

```bash
claude plugin marketplace update rocha-plugins
```

```bash
claude plugin update leis-brasil@rocha-plugins
```

As leis são atualizadas à parte, com `/leis-brasil:atualizar-leis`.

Os textos das normas são atos oficiais (art. 8º, I, da Lei 9.610/98) e têm caráter informativo:
confira sempre a fonte oficial indicada no cabeçalho de cada norma antes de citar.
