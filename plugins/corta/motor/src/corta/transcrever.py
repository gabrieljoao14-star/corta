"""Transcrição literal por palavra (mantém repetições e recomeços, que é onde estão os erros de fala).

Transcreve a voz limpa em blocos de ~30 s juntando os trechos de fala, ouvindo o ritmo real
(com as pausas), e descarta palavras fora dos trechos. Tempos no relógio do ORIGINAL.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import soundfile as sf

from .base import Cronometro, CortaErro, ler_json, log, pasta_job, salvar_json
from .perfil import carregar as carregar_perfil

PROMPT_LITERAL = {
    "pt": ("Transcrição literal, palavra por palavra, incluindo repetições, frases recomeçadas e erros: "
           "então, então eu vou, eu vou mostrar... mostrar pra você como funciona."),
    "en": "Verbatim transcript, word by word, including repetitions, restarts and mistakes: so, so I'm, I'm going to show... show you.",
    "es": "Transcripción literal, palabra por palabra, con repeticiones y frases reiniciadas: entonces, entonces yo, yo voy a mostrar...",
}

_modelos: dict = {}


def modelo(nome: str | None = None):
    from faster_whisper import WhisperModel
    p = carregar_perfil()["whisper"]
    nome = nome or os.environ.get("CORTA_MODELO") or p["modelo"]
    chave = (nome, p["device"], p["compute"])
    if chave not in _modelos:
        log(f"   carregando o modelo de transcrição {nome} (a 1ª vez baixa o modelo)…")
        _modelos[chave] = WhisperModel(nome, device=p["device"], compute_type=p["compute"])
    return _modelos[chave]


def audio16(voz: Path) -> np.ndarray:
    import scipy.signal as ss
    x, sr = sf.read(voz, dtype="float32", always_2d=True)
    return ss.resample_poly(x.mean(1), 16000, sr).astype(np.float32)


def transcrever_direto(video: Path, idioma: str = "pt") -> list[dict]:
    """Para legendar um vídeo que não passou pelas outras etapas: transcreve o áudio como está."""
    from .base import ffmpeg, rodar
    job = pasta_job(video.resolve())
    wav = job / "audio16.wav"
    rodar([ffmpeg(), "-y", "-v", "error", "-i", video, "-map", "0:a:0", "-ac", 1, "-ar", 16000, wav], descricao="extrair áudio")
    a, _ = sf.read(wav, dtype="float32")
    wav.unlink(missing_ok=True)
    c = Cronometro("transcrição")
    segs, _ = modelo().transcribe(a, language=idioma, word_timestamps=True, vad_filter=True, temperature=0)
    palavras = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                for z in segs for w in (z.words or [])]
    c.fim()
    salvar_json(job / "palavras_direto.json", palavras)
    return palavras


def transcrever(video: Path, idioma: str = "pt", nome_modelo: str | None = None) -> list[dict]:
    job = pasta_job(video.resolve())
    if not (job / "trechos.json").exists():
        raise CortaErro("Rode primeiro: corta preparar <vídeo>")
    trechos = ler_json(job / "trechos.json")["trechos"]
    a = audio16(job / "voz.wav")
    m = modelo(nome_modelo)
    c = Cronometro("transcrição")
    palavras, i = [], 0
    while i < len(trechos):
        s, j = trechos[i][0], i
        while j + 1 < len(trechos) and trechos[j + 1][1] - s < 30:
            j += 1
        e = trechos[j][1]
        ini = max(0.0, s - 0.2)
        seg = a[int(ini * 16000): int((e + 0.2) * 16000)]
        segs, _ = m.transcribe(seg, language=idioma, word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False, initial_prompt=PROMPT_LITERAL.get(idioma), temperature=0)
        for z in segs:
            for w in z.words or []:
                ws, we = ini + w.start, ini + w.end
                meio = (ws + we) / 2
                if any(c0 - 0.1 <= meio <= c1 + 0.1 for c0, c1 in trechos):
                    palavras.append({"word": w.word.strip(), "start": round(ws, 3), "end": round(we, 3)})
        log(f"   {e:.0f} s de {trechos[-1][1]:.0f} s")
        i = j + 1
    c.fim()
    salvar_json(job / "palavras.json", palavras)
    log(f"   {len(palavras)} palavras → {job / 'palavras.json'}")
    return palavras
