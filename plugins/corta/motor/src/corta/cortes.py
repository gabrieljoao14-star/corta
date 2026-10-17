"""Cortes de vídeo longo (live, podcast, aula) para Reels/Shorts/TikTok.

1. `corta texto VIDEO` mostra a transcrição inteira em frases com o tempo, para ler como roteiro.
2. O Claude escolhe os trechos (critério abaixo) e a pessoa aprova a lista ANTES de cortar.
3. `corta cortar VIDEO --cortes cortes.json --formato 9:16 --legenda creator-bold` gera cada corte
   já sem silêncio, enquadrado no rosto e legendado, numa pasta "<vídeo> - cortes".

Critério de um bom corte (nota 03, validado em 11 shorts da Aula 1):
- gancho forte nos 3 primeiros segundos; caso com virada, analogia, afirmação contra-intuitiva,
  aviso com urgência real ou recomendação específica;
- se sustenta sozinho (sem depender do slide ou da fala anterior);
- termina numa ideia completa, sem "obrigado", "próximo slide";
- 25 a 90 s depois de tirar as pausas;
- limites pela transcrição (início da 1ª palavra, fim da última), nunca "de olho".

cortes.json:
  {"cortes": [{"nome": "Prazo que ninguém conta", "inicio": "12:03.4", "fim": "12:58.0"}, …]}
(tempos em segundos ou "mm:ss.s"; os tempos são do vídeo original)
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import CortaErro, ler_json, log, nome_seguro, pasta_job, salvar_json


def _tempo(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d+):(\d+(?:[.,]\d+)?)\s*", str(v))
    if m:
        h = int(m.group(1) or 0)
        return h * 3600 + int(m.group(2)) * 60 + float(m.group(3).replace(",", "."))
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        raise CortaErro(f"Tempo '{v}' não entendido. Use segundos (734.5) ou mm:ss (12:14.5).")


def _mmss(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def frases(video: Path) -> list[dict]:
    job = pasta_job(video.resolve())
    if not (job / "palavras.json").exists():
        raise CortaErro("Rode antes: corta preparar e corta transcrever.")
    ws = ler_json(job / "palavras.json")
    out, atual = [], []
    for i, w in enumerate(ws):
        atual.append(w)
        t = w["word"].strip()
        prox = ws[i + 1]["start"] if i + 1 < len(ws) else None
        if (t and t[-1] in ".!?") or (prox is not None and prox - w["end"] > 1.2) or prox is None:
            out.append({"inicio": atual[0]["start"], "fim": atual[-1]["end"], "texto": " ".join(x["word"] for x in atual)})
            atual = []
    return out


def texto(video: Path) -> list[dict]:
    fs = frases(video)
    for f in fs:
        log(f"[{_mmss(f['inicio'])}–{_mmss(f['fim'])}] {f['texto']}")
    salvar_json(pasta_job(video.resolve()) / "frases.json", fs)
    log(f"   {len(fs)} frases")
    return fs


def cortar(video: Path, arquivo_cortes: Path, formato: str = "9:16", enquadrar: str = "rosto", zoom: str = "nao",
           legenda: str | None = None, ajustes: dict | None = None, takes: Path | None = None) -> list[Path]:
    from .legenda.queimar import legendar
    from .montar import montar
    video = video.resolve()
    lista = ler_json(arquivo_cortes)
    lista = lista.get("cortes", lista) if isinstance(lista, dict) else lista
    if not lista:
        raise CortaErro("cortes.json está vazio.")
    pasta = video.with_name(f"{video.stem} - cortes")
    pasta.mkdir(exist_ok=True)
    feitos = []
    for n, c in enumerate(lista, 1):
        ini, fim = _tempo(c["inicio"]), _tempo(c["fim"])
        if fim <= ini:
            raise CortaErro(f"Corte {n} ('{c.get('nome', '')}'): o fim vem antes do início.")
        nome = f"{n:02d} - {nome_seguro(c.get('nome') or f'corte {n}')}"
        log(f"\n######## corte {n}/{len(lista)}: {nome} [{_mmss(ini)}–{_mmss(fim)}]")
        saida = montar(video, takes=takes, apertar=True, saida=pasta / f"{nome}.mp4", formato=formato,
                       enquadrar=enquadrar, zoom=zoom, janela=(ini, fim))
        if legenda:
            final = legendar(saida, estilo=legenda, ajustes=ajustes or {}, saida=pasta / f"{nome} (legendado).mp4")
            feitos.append(final)
        else:
            feitos.append(saida)
    log(f"\n{len(feitos)} cortes em: {pasta}")
    return feitos
