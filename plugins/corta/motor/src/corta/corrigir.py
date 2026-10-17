"""Corrige palavras que o Whisper errou ("lerite" → "holerite", "Cloud" → "Claude").

Corrige nos DOIS lugares de uma vez (nota 04: o motor usa as palavras com tempo, então corrigir só o
texto não adianta): as palavras do original e as da montagem. Mantém a pontuação colada na palavra.
Uma correção pode juntar palavras: "lei rite=holerite" troca as duas pela palavra nova.
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import CortaErro, ler_json, log, pasta_job, saida_registrada, salvar_json

PONTA = ".,;:!?…\"“”()"


def _separa(t: str):
    m = re.match(rf"^([{re.escape(PONTA)}]*)(.*?)([{re.escape(PONTA)}]*)$", t.strip())
    return m.group(1), m.group(2), m.group(3)


def _aplicar(palavras: list[dict], errado: list[str], certo: str) -> tuple[list[dict], int]:
    n, out, i, trocas = len(errado), [], 0, 0
    alvo = [e.lower() for e in errado]
    while i < len(palavras):
        miolos = [_separa(w["word"])[1].lower() for w in palavras[i: i + n]]
        if miolos == alvo:
            pre = _separa(palavras[i]["word"])[0]
            pos = _separa(palavras[i + n - 1]["word"])[2]
            out.append({"word": pre + certo + pos, "start": palavras[i]["start"], "end": palavras[i + n - 1]["end"]})
            i += n
            trocas += 1
        else:
            out.append(palavras[i])
            i += 1
    return out, trocas


def corrigir(video: Path, correcoes: list[str]) -> int:
    video = video.resolve()
    arquivos = []
    reg = saida_registrada(video)
    if reg and reg.get("palavras"):
        arquivos.append(Path(reg["palavras"]))
        if reg.get("job") and (Path(reg["job"]) / "palavras.json").exists():
            arquivos.append(Path(reg["job"]) / "palavras.json")
    job = pasta_job(video)
    for nome in ("palavras.json", "palavras_saida.json", "palavras_direto.json"):
        if (job / nome).exists():
            arquivos.append(job / nome)
    arquivos = list(dict.fromkeys(arquivos))
    if not arquivos:
        raise CortaErro("Não achei palavras desse vídeo. Rode antes: corta transcrever (ou corta legendar).")
    total = 0
    for c in correcoes:
        if "=" not in c:
            raise CortaErro(f"Correção '{c}' precisa ser errado=certo (ex.: lerite=holerite).")
        errado, certo = c.split("=", 1)
        partes = errado.split()
        for arq in arquivos:
            novas, n = _aplicar(ler_json(arq), partes, certo.strip())
            if n:
                salvar_json(arq, novas)
                total += n
                log(f"   {errado} → {certo.strip()}: {n}× em {arq.name}")
    if not total:
        log("   nenhuma ocorrência encontrada")
    return total
