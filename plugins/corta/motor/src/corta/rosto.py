"""Onde está o rosto de quem fala, ao longo do vídeo. Usado para enquadrar (16:9 → 9:16 seguindo
o rosto) e para o zoom aproximar no rosto, não no meio da tela.

Detector YuNet (OpenCV, licença MIT, modelo de 230 KB no plugin): roda igual no Mac e no Windows,
no lugar do Apple Vision das primeiras versões. Mede 4 quadros por segundo em baixa resolução e
guarda em `rosto.json` na pasta do vídeo, para não medir de novo.
"""
from __future__ import annotations

import subprocess

import numpy as np

from .base import RAIZ_PLUGIN, CortaErro, ffmpeg, info_video, ler_json, log, pasta_job, salvar_json

MODELO = RAIZ_PLUGIN / "assets" / "modelos" / "face_detection_yunet_2023mar.onnx"
PASSO = 0.25
LARGURA = 640


def _medir(video, ini: float, fim: float, info: dict) -> list[list[float]]:
    """Roda o detector num processo separado: o OpenCV e o Whisper trazem cópias diferentes das
    bibliotecas do ffmpeg e, no Mac, carregar os dois no mesmo processo pode travar."""
    import json
    import sys
    if not MODELO.exists():
        raise CortaErro("Modelo de rosto não encontrado no plugin. Reinstale o /corta.")
    r = subprocess.run([sys.executable, "-m", "corta.rosto", str(video), f"{ini:.3f}", f"{fim:.3f}",
                        str(info["largura"]), str(info["altura"])], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise CortaErro("O detector de rosto falhou.\n" + r.stderr[-1500:])
    return json.loads(r.stdout)


def _medir_aqui(video: str, ini: float, fim: float, largura: int, altura: int) -> list[list[float]]:
    import cv2
    w = LARGURA
    h = int(round(altura * w / largura / 2) * 2)
    det = cv2.FaceDetectorYN.create(str(MODELO), "", (w, h), 0.6, 0.3, 5000)
    proc = subprocess.Popen([ffmpeg(), "-v", "error", "-hwaccel", "auto", "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", video,
                             "-vf", f"fps={1 / PASSO},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    tam, k, out = w * h * 3, 0, []
    while True:
        buf = proc.stdout.read(tam)
        if len(buf) < tam:
            break
        quadro = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        _, faces = det.detect(quadro)
        t = round(ini + k * PASSO, 3)
        if faces is not None and len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4]
            out.append([t, round(float((x + fw / 2) / w), 4), round(float((y + fh / 2) / h), 4), round(float(fh / h), 4)])
        else:
            out.append([t, None, None, None])
        k += 1
    proc.wait()
    return out


def amostras(video, ini: float, fim: float) -> list[list]:
    """[[t, cx, cy, altura_do_rosto], …] em frações do quadro (None quando não acha rosto)."""
    video = video.resolve()
    ini = max(0.0, np.floor(ini / PASSO) * PASSO)   # grade fixa: medições de chamadas diferentes se reaproveitam
    job = pasta_job(video)
    arq = job / "rosto.json"
    cache = {round(a[0], 2): a for a in (ler_json(arq) if arq.exists() else [])}
    faltam = [t for t in np.arange(ini, fim, PASSO) if round(float(t), 2) not in cache]
    if faltam:
        info = info_video(video)
        a, b = float(faltam[0]), min(float(faltam[-1]) + PASSO, info["duracao"])
        log(f"   procurando o rosto de {a:.0f} s a {b:.0f} s…")
        for item in _medir(video, a, b, info):
            cache[round(item[0], 2)] = item
        salvar_json(arq, sorted(cache.values()))
    return [cache[k] for k in sorted(cache) if ini - PASSO <= k <= fim]


def posicao(lista: list[list], a: float, b: float, padrao=(0.5, 0.4)) -> tuple[float, float, bool]:
    """Posição mediana do rosto entre a e b. Sem rosto nesse intervalo, usa o vizinho mais próximo."""
    dentro = [x for x in lista if a <= x[0] <= b and x[1] is not None]
    if not dentro:
        com = [x for x in lista if x[1] is not None]
        if not com:
            return padrao[0], padrao[1], False
        meio = (a + b) / 2
        dentro = [min(com, key=lambda x: abs(x[0] - meio))]
    return float(np.median([x[1] for x in dentro])), float(np.median([x[2] for x in dentro])), True


if __name__ == "__main__":
    import json
    import sys
    v, a, b, lw, lh = sys.argv[1:6]
    print(json.dumps(_medir_aqui(v, float(a), float(b), int(lw), int(lh))))
