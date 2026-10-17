"""Lista numerada dos trechos de fala com o texto, para decidir os takes.

Trechos suspeitos também são transcritos ISOLADOS: em bloco o Whisper funde recomeços
("Desde… Desde 1973" vira um "Desde" só). As duas leituras lado a lado mostram o recomeço.
Suspeito = sinais das notas 01 (rodadas de 30/09, 07/10 e 15/10):
- frase que dura muito mais do que devia para o número de palavras (recomeço escondido);
- palavra curta esticada (o "é" de 0,8 s em "A aula é gra— / A aula é gratuita");
- palavra repetida em sequência ("Quem? Quem", "a cobrança, a cobrança");
- trecho curto (falso início solto).
Transcrever todos isolados é mais seguro e bem mais lento (cada um custa uma janela inteira do Whisper).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .base import Cronometro, CortaErro, ler_json, log, pasta_job, salvar_json
from .transcrever import audio16, modelo


def _norm(p: str) -> str:
    return re.sub(r"[^\wà-ú]", "", p.lower())


def _suspeitas(ws: list[dict], dur: float) -> list[str]:
    motivos = []
    if not ws:
        return ["sem texto"]
    if dur < 1.2:
        motivos.append("curto")
    if dur / len(ws) > 0.65 and dur > 1.5:
        motivos.append("lento para o nº de palavras")
    for w in ws:
        if len(_norm(w["word"])) <= 3 and w["end"] - w["start"] > 0.6:
            motivos.append(f"'{w['word']}' esticada")
            break
    n = [_norm(w["word"]) for w in ws]
    for k in range(1, len(n)):
        if n[k] and n[k] == n[k - 1]:
            motivos.append(f"repete '{ws[k]['word']}'")
            break
        if k >= 3 and n[k - 1: k + 1] == n[k - 3: k - 1] and n[k]:
            motivos.append("repete duas palavras")
            break
    return motivos


def listar(video: Path, isolado: str = "auto", idioma: str = "pt") -> list[dict]:
    job = pasta_job(video.resolve())
    if not (job / "palavras.json").exists():
        raise CortaErro("Rode primeiro: corta transcrever <vídeo>")
    palavras = ler_json(job / "palavras.json")
    trechos = ler_json(job / "trechos.json")["trechos"]

    # cada palavra vai para o trecho que contém o meio dela (ou o mais próximo)
    por_trecho: list[list[dict]] = [[] for _ in trechos]
    for w in palavras:
        meio = (w["start"] + w["end"]) / 2
        i = min(range(len(trechos)), key=lambda j: 0 if trechos[j][0] <= meio <= trechos[j][1]
                else min(abs(meio - trechos[j][0]), abs(meio - trechos[j][1])))
        por_trecho[i].append(w)

    a = m = None
    c = Cronometro("leitura dos trechos")
    saida, n_iso = [], 0
    for i, (s, e) in enumerate(trechos):
        ws = por_trecho[i]
        item = {"i": i, "inicio": s, "fim": e, "texto": " ".join(w["word"] for w in ws),
                "suspeita": _suspeitas(ws, e - s)}
        if isolado == "todos" or (isolado == "auto" and item["suspeita"]):
            if m is None:
                a, m = audio16(job / "voz.wav"), modelo()
            pad = np.zeros(8000, np.float32)
            seg = np.concatenate([pad, a[int(s * 16000): int(e * 16000)], pad])
            r = m.transcribe(seg, language=idioma, vad_filter=False, condition_on_previous_text=False, temperature=0)[0]
            item["isolado"] = " ".join(z.text.strip() for z in r).strip()
            n_iso += 1
        saida.append(item)
        extra = ""
        if item["suspeita"]:
            extra += f"  ⚠ {', '.join(item['suspeita'])}"
        if "isolado" in item:
            extra += f"  ‖ isolado: {item['isolado'] or '(nada)'}"
        log(f"T{i:03d} [{s:7.2f}–{e:7.2f}] {item['texto']}{extra}")
    c.fim()
    log(f"   {len(trechos)} trechos · {n_iso} lidos isolados · lista em {job / 'trechos_texto.json'}")
    salvar_json(job / "trechos_texto.json", saida)
    return saida
