"""Etapa 1: voz limpa + onde tem fala. Não gera vídeo: só os dados que as outras etapas usam.

Método validado nos criativos (nota 01): a fala é decidida por detector de voz (Silero VAD) na voz
limpa, não pelo volume. Barulho baixo sai, pausa entre frases sai, e trecho "de fala" que nunca passa
de −30 dB (voz de fundo, respiração antes do take) também sai. Mantém todos os takes, inclusive os
errados: escolher o take certo é a etapa seguinte.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from .base import Cronometro, CortaErro, conferir_arquivo_local, ffmpeg, info_video, log, pasta_job, rodar, salvar_json

SR = 48000
LUFS = -16
VAD_LIMIAR = 0.5          # 0,35 deixava passar estalos
PICO_MIN_DB = -30         # "fala" que nunca chega aqui é voz de fundo / barulho
RITMOS = {                # folga antes/depois de cada fala
    "rapido": (0.05, 0.10),   # Reels e criativos: emenda frase com frase
    "natural": (0.15, 0.25),  # aula e YouTube: pausa curta demais cansa em 60 min
}
FILTROS_VOZ = {
    "nao": "",
    "leve": "highpass=f=70,afftdn=nr=12:nf=-50",
    "forte": "highpass=f=70",   # o Demucs já tirou o ruído
}


def _loudnorm(entrada: Path, saida: Path, pre: str) -> None:
    """Volume em −16 LUFS em 2 passadas (linear: não 'bombeia')."""
    base = f"{pre}," if pre else ""
    m = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(entrada), "-af",
                        f"{base}loudnorm=I={LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        js = json.loads(m.stderr[m.stderr.rindex("{"): m.stderr.rindex("}") + 1])
        ln = (f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
              f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    except (ValueError, KeyError):
        ln = f"loudnorm=I={LUFS}:TP=-1.5:LRA=11"
    rodar([ffmpeg(), "-y", "-v", "error", "-i", entrada, "-af", base + ln, "-ar", SR, "-ac", 2,
           "-c:a", "pcm_s16le", saida], descricao="volume da voz")


def _demucs(raw: Path, job: Path) -> Path:
    try:
        import demucs  # noqa: F401
    except ImportError:
        raise CortaErro("A limpeza forte não está instalada neste computador. Use voz=leve, ou rode /corta:instalar e escolha a limpeza forte.")
    out = job / "demucs"
    r = subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "--out", str(out), str(raw)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    voc = out / "htdemucs" / raw.stem / "vocals.wav"
    if r.returncode != 0 or not voc.exists():
        raise CortaErro("A limpeza forte (Demucs) falhou. Tente voz=leve.\n" + r.stderr[-1500:])
    return voc


def voz_limpa(video: Path, job: Path, modo: str) -> Path:
    if modo not in FILTROS_VOZ:
        raise CortaErro(f"voz='{modo}' não existe. Use: leve, forte ou nao.")
    raw = job / "audio_original.wav"
    rodar([ffmpeg(), "-y", "-v", "error", "-i", video, "-map", "0:a:0", "-ac", 2, "-ar", SR, "-c:a", "pcm_s16le", raw],
          descricao="extrair áudio")
    fonte = _demucs(raw, job) if modo == "forte" else raw
    voz = job / "voz.wav"
    _loudnorm(fonte, voz, FILTROS_VOZ[modo])
    raw.unlink(missing_ok=True)
    return voz


def _db(x: np.ndarray, jan: int) -> np.ndarray:
    n = len(x) // jan
    if not n:
        return np.array([-120.0])
    return 20 * np.log10(np.sqrt((x[: n * jan].reshape(n, jan) ** 2).mean(1)) + 1e-9)


def trechos_de_fala(voz: Path, duracao: float, ritmo: str) -> list[list[float]]:
    import scipy.signal as ss
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    antes, depois = RITMOS[ritmo]
    x, sr = sf.read(voz, dtype="float32", always_2d=True)
    a16 = ss.resample_poly(x.mean(1), 16000, sr).astype(np.float32)
    ts = get_speech_timestamps(a16, VadOptions(threshold=VAD_LIMIAR, min_speech_duration_ms=120,
                                               min_silence_duration_ms=100, speech_pad_ms=0))
    manter: list[list[float]] = []
    for t in ts:
        if _db(a16[t["start"]: t["end"]], 320).max() < PICO_MIN_DB:
            continue
        s = max(0.0, t["start"] / 16000 - antes)
        e = min(duracao, t["end"] / 16000 + depois)
        if manter and s <= manter[-1][1] + 0.05:
            manter[-1][1] = max(manter[-1][1], e)
        else:
            manter.append([s, e])
    return [[round(s, 3), round(e, 3)] for s, e in manter]


def preparar(video: Path, voz: str = "leve", ritmo: str = "rapido") -> dict:
    video = video.resolve()
    conferir_arquivo_local(video)
    if ritmo not in RITMOS:
        raise CortaErro(f"ritmo='{ritmo}' não existe. Use: rapido ou natural.")
    info = info_video(video)
    if not info["tem_audio"]:
        raise CortaErro(f"{video.name} não tem som: não dá para achar a fala.")
    job = pasta_job(video)
    log(f"== {video.name} · {info['largura']}x{info['altura']} · {info['fps']:.2f} fps · {info['duracao']:.1f} s")
    c = Cronometro("voz limpa")
    arq_voz = voz_limpa(video, job, voz)
    c.fim()
    c = Cronometro("detectar fala")
    trechos = trechos_de_fala(arq_voz, info["duracao"], ritmo)
    c.fim()
    if not trechos:
        raise CortaErro("Não encontrei fala nesse vídeo. Confira se o áudio é a voz de quem fala.")
    mantido = sum(e - s for s, e in trechos)
    dados = {"video": str(video), "info": info, "voz": voz, "ritmo": ritmo, "trechos": trechos}
    salvar_json(job / "trechos.json", dados)
    log(f"   {len(trechos)} trechos de fala · {mantido:.1f} s de {info['duracao']:.1f} s (sai {info['duracao'] - mantido:.1f} s de pausa e barulho)")
    log(f"   dados em: {job}")
    return dados
