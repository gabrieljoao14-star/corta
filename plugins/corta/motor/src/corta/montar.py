"""Etapa 2: monta o vídeo só com o que fica, direto do ORIGINAL, numa passada só.

- Sem `takes.json`: fica toda a fala (só tira silêncio e barulho).
- Com `takes.json` ({"manter": [3, 4, [7, 12.40, null], …]}): fica só o que o Claude e a pessoa decidiram.
  Número = trecho inteiro; [trecho, início, fim] = corta dentro do trecho (null mantém a borda).
- `apertar`: mede pela energia da voz onde cada fala começa e termina e corta pausa interna > 0,22 s,
  sem criar corte < 0,15 s (vira "pulo" de imagem). Ligado por padrão no ritmo rápido.

Sincronia por construção (nota 01/04): cortes na grade de quadros (cada quadro = N amostras exatas),
vídeo por select=between(n,…) em árvore balanceada e áudio fatiado na amostra com fade de 8 ms.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from .base import (Cronometro, CortaErro, ffmpeg, fps_saida, ler_json, log, pasta_job, registrar_saida, rodar,
                   saida_livre, salvar_json)
from .perfil import args_video, carregar as carregar_perfil

LIMIAR_VOZ_DB = -42     # acima disso é voz (a −45 entra respiração)
BORDA_DB = -45          # para recuperar consoante que o VAD cortou ("Clica" virava "lica")
BORDA_MAX = 0.30
JANELA = 0.01
REGIAO_MIN = 0.06       # som mais curto que isso é estalo
PAUSA_MAX = 0.22        # pausa interna maior que isso é cortada
ANTES, DEPOIS = 0.06, 0.09
CORTE_MIN = 0.15
FADE = 0.008


def _db_em(x: np.ndarray, sr: int, t: float) -> float:
    n = int(JANELA * sr)
    seg = x[max(0, int(t * sr)): max(0, int(t * sr)) + n]
    return float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)) if len(seg) else -120.0


def _refinar(x, sr, s, e):
    t = s
    while t > max(0.0, s - BORDA_MAX) and _db_em(x, sr, t - JANELA) > BORDA_DB:
        t -= JANELA
    s2 = max(0.0, min(s, t - 0.03))
    t = e
    while t < e + BORDA_MAX and _db_em(x, sr, t) > BORDA_DB:
        t += JANELA
    return s2, max(e, t + 0.03)


def _regioes(x, sr, a, b):
    n = int(JANELA * sr)
    seg = x[int(a * sr): int(b * sr)]
    k = len(seg) // n
    if not k:
        return []
    on = 20 * np.log10(np.sqrt((seg[: k * n].reshape(k, n) ** 2).mean(1)) + 1e-9) > LIMIAR_VOZ_DB
    out, i = [], 0
    while i < k:
        if on[i]:
            j = i
            while j < k and on[j]:
                j += 1
            out.append([a + i * JANELA, a + j * JANELA])
            i = j
        else:
            i += 1
    juntos = []
    for r in out:
        if juntos and r[0] - juntos[-1][1] <= PAUSA_MAX:
            juntos[-1][1] = r[1]
        else:
            juntos.append(r)
    return [r for r in juntos if r[1] - r[0] >= REGIAO_MIN]


def _intervalos(trechos, plano, x, sr, apertar: bool):
    itens = sorted(plano, key=lambda it: it if isinstance(it, int) else it[0])
    brutos = []
    for it in itens:
        i, so, eo = (it, None, None) if isinstance(it, int) else (it[0], it[1], it[2])
        if not 0 <= i < len(trechos):
            raise CortaErro(f"takes.json fala do trecho {i}, mas só existem {len(trechos)} (T000–T{len(trechos) - 1:03d}).")
        if apertar:
            a = so if so is not None else trechos[i][0] - 0.3
            b = eo if eo is not None else trechos[i][1] + 0.3
            pecas = []
            for s, e in _regioes(x, sr, max(0.0, a), b):
                s2, e2 = max(a, s - ANTES), min(b, e + DEPOIS)
                if pecas and s2 - pecas[-1][1] < CORTE_MIN:
                    pecas[-1][1] = e2
                else:
                    pecas.append([s2, e2])
            if pecas:
                brutos.extend(pecas)
                continue
        s, e = _refinar(x, sr, *trechos[i])
        brutos.append([so if so is not None else s, eo if eo is not None else e])
    juntos = []
    for s, e in sorted(brutos):
        if juntos and s <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], e)
        else:
            juntos.append([max(0.0, s), e])
    return juntos


def _arvore(termos):
    # a soma linear "a+b+c…" estoura o parser do ffmpeg com > ~100 termos
    if len(termos) == 1:
        return termos[0]
    m = len(termos) // 2
    return f"({_arvore(termos[:m])}+{_arvore(termos[m:])})"


def montar(video: Path, takes: Path | None = None, apertar: bool | None = None, saida: Path | None = None) -> Path:
    video = video.resolve()
    job = pasta_job(video)
    if not (job / "trechos.json").exists():
        raise CortaErro("Rode primeiro: corta preparar <vídeo>")
    dados = ler_json(job / "trechos.json")
    trechos, info = dados["trechos"], dados["info"]
    plano = ler_json(takes)["manter"] if takes else list(range(len(trechos)))
    if apertar is None:
        apertar = dados["ritmo"] == "rapido"
    perfil = carregar_perfil()
    F = fps_saida(info["fps"])
    voz, sr = sf.read(job / "voz.wav", dtype="float32", always_2d=True)
    mono = voz.mean(1)
    spf = sr // F

    intervalos = _intervalos(trechos, plano, mono, sr, apertar)
    quadros = [(int(round(s * F)), int(round(e * F))) for s, e in intervalos]
    quadros = [(a, b) for a, b in quadros if b > a]
    if not quadros:
        raise CortaErro("Nada para montar: a lista de takes ficou vazia.")

    fade = int(FADE * sr)
    rampa = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    pedacos, mapa, t_out = [], [], 0.0
    for a, b in quadros:
        p = voz[a * spf: b * spf].copy()
        falta = (b - a) * spf - len(p)
        if falta > 0:
            p = np.vstack([p, np.zeros((falta, p.shape[1]), np.float32)])
        p[:fade] *= rampa
        p[-fade:] *= rampa[::-1]
        pedacos.append(p)
        dur = (b - a) / F
        mapa.append({"original": [a / F, b / F], "saida": [round(t_out, 4), round(t_out + dur, 4)]})
        t_out += dur
    wav = job / "audio_montado.wav"
    sf.write(wav, np.vstack(pedacos), sr, subtype="PCM_16")

    expr = _arvore([f"between(n,{a},{b - 1})" for a, b in quadros])
    filtro = job / "filtro_select.txt"
    filtro.write_text(f"[0:v:0]fps={F},select='{expr}',setpts=N/{F}/TB[v]", encoding="utf-8")
    saida = saida_livre(Path(saida) if saida else video.with_name(f"{video.stem} (editado).mp4"))
    log(f"== montando {len(quadros)} pedaços · {t_out:.1f} s · {F} fps · {perfil['encoder']}")
    c = Cronometro("montagem")
    rodar([ffmpeg(), "-y", "-v", "error", "-i", video, "-i", wav, "-/filter_complex", filtro,
           "-map", "[v]", "-map", "1:a:0", *args_video(perfil), "-r", F,
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida], descricao="montagem do vídeo")
    c.fim()
    wav.unlink(missing_ok=True)

    palavras_saida = []
    if (job / "palavras.json").exists():
        for w in ler_json(job / "palavras.json"):
            meio = (w["start"] + w["end"]) / 2
            for m in mapa:
                s0, e0 = m["original"]
                if s0 <= meio < e0:
                    off = m["saida"][0] - s0
                    palavras_saida.append({"word": w["word"], "start": round(max(s0, w["start"]) + off, 3),
                                           "end": round(min(e0, w["end"]) + off, 3)})
                    break
    salvar_json(job / "mapa.json", {"fps": F, "apertar": apertar, "takes": str(takes) if takes else None, "mapa": mapa})
    salvar_json(job / "palavras_saida.json", palavras_saida)
    registrar_saida(job, {"arquivo": str(saida.resolve()), "etapa": "montar", "palavras": str(job / "palavras_saida.json"),
                          "mapa": str(job / "mapa.json")})
    log(f"   → {saida}")
    return saida
