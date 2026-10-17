"""Onde estão a TELA e a CÂMERA numa gravação de aula/tutorial (Zoom, Meet, OBS), para o layout
vertical "tela em cima, faixa da legenda no meio, câmera embaixo".

Automático: mediana de ~15 quadros (tira cursor e movimento), áreas que não são fundo preto viram
blocos; o bloco que contém o rosto é a câmera e o maior dos outros é a tela. Sai sempre uma imagem
com as caixas desenhadas (`regioes.png`) para o Claude olhar antes de cortar. Se errar, dá para
passar as caixas à mão num JSON: {"tela": [x, y, largura, altura], "camera": [x, y, largura, altura]}
em pixels do vídeo original.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .base import CortaErro, ffmpeg, info_video, ler_json, log, pasta_job, salvar_json

PRETO = 28          # abaixo disso (0–255) é fundo
AREA_MIN = 0.01     # bloco menor que 1 % do quadro é ruído (nome, ícone)


def _quadros(video: Path, ini: float, fim: float, n: int, w: int, h: int) -> np.ndarray:
    out = []
    for t in np.linspace(ini, max(ini, fim - 0.5), n):
        b = subprocess.run([ffmpeg(), "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(b) >= w * h:
            out.append(np.frombuffer(b[: w * h], np.uint8).reshape(h, w))
    if not out:
        raise CortaErro("Não consegui ler quadros do vídeo para achar a tela e a câmera.")
    return np.median(np.stack(out), axis=0).astype(np.uint8)


def _aparar(img: np.ndarray, caixa: list[int], densidade: float = 0.012) -> list[int]:
    """Tira das laterais as colunas sem conteúdo (barra do programa, margem, rolagem): o texto da tela
    fica maior no vertical. Conteúdo = densidade de bordas (texto, imagem) na coluna. Nunca tira mais
    da metade da largura."""
    x, y, w, h = caixa
    reg = img[y: y + h, x: x + w].astype(np.int16)
    bordas = (np.abs(np.diff(reg, axis=0)) > 25).mean(axis=0)
    suave = np.convolve(bordas, np.ones(31) / 31, mode="same")
    idx = np.where(suave > densidade)[0]
    if not len(idx):
        return caixa
    a, b = max(0, idx[0] - int(w * 0.04)), min(w, idx[-1] + int(w * 0.04))
    if b - a < w * 0.5:
        return caixa
    return [x + a // 2 * 2, y, (b - a) // 2 * 2, h]


def detectar(video: Path, ini: float = 0.0, fim: float | None = None) -> dict:
    from scipy import ndimage
    from .rosto import amostras, posicao
    video = video.resolve()
    info = info_video(video)
    W, H = info["largura"], info["altura"]
    fim = info["duracao"] if fim is None else fim
    mediana = _quadros(video, ini, fim, 15, W, H)
    rot, n = ndimage.label(mediana > PRETO)
    blocos = []
    for i, fatia in enumerate(ndimage.find_objects(rot), 1):
        ys, xs = fatia
        area = (ys.stop - ys.start) * (xs.stop - xs.start)
        if area >= AREA_MIN * W * H:
            blocos.append({"caixa": [xs.start, ys.start, xs.stop - xs.start, ys.stop - ys.start], "area": area})
    amos = amostras(video, ini, min(fim, ini + 15))
    fx, fy, achou = posicao(amos, ini, min(fim, ini + 15))
    if not achou:
        raise CortaErro("Não achei rosto nessa gravação: o layout tela + câmera precisa da câmera de quem fala.")
    px, py = fx * W, fy * H
    dentro = lambda c: c[0] <= px <= c[0] + c[2] and c[1] <= py <= c[1] + c[3]
    cams = [b for b in blocos if dentro(b["caixa"])]
    estimado = False
    if cams and cams[0]["area"] < 0.5 * W * H:
        cam = min(cams, key=lambda b: b["area"])["caixa"]
        outros = [b for b in blocos if b["caixa"] != cam and not dentro(b["caixa"])]
        if not outros:
            raise CortaErro("Achei a câmera mas não a tela. Passe as caixas à mão (--regioes).")
        tela = max(outros, key=lambda b: b["area"])["caixa"]
    else:
        # sem fundo preto separando: estima a câmera em volta do rosto e a tela no maior lado livre
        estimado = True
        alt_rosto = np.median([a[3] for a in amos if a[3]]) * H
        cw, ch = int(alt_rosto * 3.2), int(alt_rosto * 2.4)
        cam = [int(max(0, min(W - cw, px - cw / 2))), int(max(0, min(H - ch, py - ch * 0.45))), cw, ch]
        lados = [[0, 0, cam[0], H], [cam[0] + cw, 0, W - cam[0] - cw, H], [0, 0, W, cam[1]], [0, cam[1] + ch, W, H - cam[1] - ch]]
        tela = max(lados, key=lambda c: c[2] * c[3])
    tela = _aparar(mediana, tela)
    reg = {"tela": [int(v) for v in tela], "camera": [int(v) for v in cam], "estimado": estimado,
           "rosto": [round(fx, 4), round(fy, 4)], "video": [W, H]}
    job = pasta_job(video)
    salvar_json(job / "regioes.json", reg)
    img = Image.fromarray(mediana).convert("RGB")
    d = ImageDraw.Draw(img)
    for nome, cor in (("tela", (60, 140, 255)), ("camera", (255, 200, 40))):
        x, y, w, h = reg[nome]
        d.rectangle((x, y, x + w - 1, y + h - 1), outline=cor, width=max(3, W // 300))
        d.text((x + 8, y + 8), nome.upper(), fill=cor)
    img.save(job / "regioes.png")
    log(f"   tela {reg['tela']} · câmera {reg['camera']}{' (estimada: confira)' if estimado else ''}")
    log(f"   confira as caixas em: {job / 'regioes.png'}")
    return reg


def carregar(video: Path, arquivo: Path | None, janela: tuple[float, float] | None) -> dict:
    if arquivo:
        r = ler_json(arquivo)
        if "tela" not in r or "camera" not in r:
            raise CortaErro("O arquivo de regiões precisa ter 'tela' e 'camera' ([x, y, largura, altura]).")
        return r
    job = pasta_job(video.resolve())
    if (job / "regioes.json").exists():
        return ler_json(job / "regioes.json")
    return detectar(video, *(janela or (0.0, None)))
