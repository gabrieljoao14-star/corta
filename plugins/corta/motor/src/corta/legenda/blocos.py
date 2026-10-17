"""Divide as palavras em blocos curtos e calcula quando cada palavra fica ativa.

Regras validadas nos criativos e cortes (notas 01 e 03):
- até N palavras por bloco; quebra em pausa > 0,5 s e em fim de frase;
- sem pontuação nas pontas (mantém ? e números como 1.200 e R$ 9.000);
- token que começa com "-" é unido ao anterior ("e" + "-mail");
- palavra que fecha a frase não fica sozinha no começo do bloco seguinte;
- bloco não termina em artigo/preposição quando dá para passar a palavra para o próximo.
"""
from __future__ import annotations

PAUSA = 0.5
PONTA = ".,;:!…\"“”()[]{}—–-'"
FRACAS = {"a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos",
          "nas", "e", "que", "pra", "para", "com", "por", "pelo", "pela", "se", "ao", "à", "meu", "minha", "seu", "sua",
          "the", "of", "to", "and", "el", "la", "los", "las", "y"}


def limpar_palavra(t: str) -> str:
    return t.strip().lstrip(PONTA).rstrip(PONTA)


def unir_hifens(palavras: list[dict]) -> list[dict]:
    out = []
    for w in palavras:
        t = w["word"].strip()
        if t.startswith("-") and len(t) > 1 and out:
            out[-1]["word"] = out[-1]["word"].rstrip() + t
            out[-1]["end"] = w["end"]
        else:
            out.append(dict(w))
    return out


def montar_blocos(palavras: list[dict], maximo: int) -> list[list[dict]]:
    ws = [w for w in unir_hifens(palavras) if limpar_palavra(w["word"])]
    blocos, atual = [], []
    for w in ws:
        t = w["word"].strip()
        if atual and w["start"] - atual[-1]["end"] >= PAUSA:
            blocos.append(atual)
            atual = []
        fecha = t[-1] in ".!?,;:"
        # palavra que fecha frase e cairia sozinha no bloco seguinte vai para o anterior (até N+1)
        if (not atual and fecha and blocos and maximo > 1 and len(blocos[-1]) <= maximo
                and blocos[-1][-1]["word"].strip()[-1] not in ".!?" and w["start"] - blocos[-1][-1]["end"] < PAUSA):
            blocos[-1].append(w)
            continue
        atual.append(w)
        if (fecha and (len(atual) >= 2 or t[-1] in ".!?")) or len(atual) >= maximo:
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    # não terminar em palavra fraca: passa para o começo do próximo bloco
    if maximo > 1:
        for i in range(len(blocos) - 1):
            b, prox = blocos[i], blocos[i + 1]
            if (len(b) > 1 and limpar_palavra(b[-1]["word"]).lower() in FRACAS
                    and prox[0]["start"] - b[-1]["end"] < PAUSA and len(prox) < maximo + 1):
                prox.insert(0, b.pop())
    return [b for b in blocos if b]


def linha_do_tempo(blocos: list[list[dict]], duracao: float) -> list[dict]:
    """Para cada bloco: início, fim e o intervalo em que cada palavra está ativa."""
    out = []
    for i, b in enumerate(blocos):
        ini = b[0]["start"]
        prox = blocos[i + 1][0]["start"] if i + 1 < len(blocos) else None
        fim_fala = b[-1]["end"]
        if prox is not None and prox - fim_fala <= 0.6:
            fim = prox
        else:
            fim = min(fim_fala + 0.3, prox if prox is not None else duracao)
        fim = min(fim, duracao)
        ativos = []
        for k, w in enumerate(b):
            a = w["start"]
            z = b[k + 1]["start"] if k + 1 < len(b) else fim
            ativos.append((max(ini, a), max(a, z)))
        out.append({"inicio": ini, "fim": fim, "palavras": [limpar_palavra(w["word"]) for w in b], "ativos": ativos})
    return out
