"""Queima a legenda no vídeo: desenha cada estado (bloco + palavra ativa + animação) como imagem,
monta uma lista com a duração de cada uma e cola por cima do vídeo com o ffmpeg numa passada.

As palavras vêm, em ordem de preferência: --palavras; a montagem que gerou este vídeo
(tempos já remapeados); a transcrição deste próprio vídeo.
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

from PIL import Image

from ..base import (Cronometro, CortaErro, conferir_arquivo_local, ffmpeg, info_video, ler_json, log, pasta_job,
                    registrar_saida, nome_seguro, rodar, saida_livre, saida_registrada, salvar_json)
from ..perfil import args_video, carregar as carregar_perfil
from .blocos import linha_do_tempo, montar_blocos
from .desenho import Desenhista
from .estilos import carregar_estilo

DUR_ANIM = {"pop": 0.18, "pulo": 0.32, "aparecer": 0.20, "subir": 0.22, "nenhuma": 0.0}
PASSO_ANIM = 1 / 30


def achar_palavras(video: Path, palavras: Path | None, idioma: str) -> tuple[list[dict], str]:
    if palavras:
        return ler_json(palavras), str(palavras)
    reg = saida_registrada(video)
    if reg and reg.get("palavras") and Path(reg["palavras"]).exists():
        return ler_json(reg["palavras"]), reg["palavras"]
    job = pasta_job(video.resolve())
    if (job / "palavras.json").exists() and not (job / "mapa.json").exists():
        return ler_json(job / "palavras.json"), str(job / "palavras.json")
    from ..transcrever import transcrever_direto
    log("   este vídeo não passou pela montagem: transcrevendo o áudio dele")
    return transcrever_direto(video, idioma), "transcrição direta"


def _eventos(est: dict, tl: list[dict], des: Desenhista, pasta: Path):
    """Lista (início, fim, arquivo) cobrindo os momentos com legenda."""
    cache: dict = {}
    n_img = [0]

    def salvar(img: Image.Image) -> str:
        nome = f"{n_img[0]:05d}.png"
        img.save(pasta / nome, compress_level=1)
        n_img[0] += 1
        return nome

    def estado(bi: int, ativa: int | None) -> str:
        if est["tipo_destaque"] == "nenhum":
            ativa = None
        if (bi, ativa) not in cache:
            cache[(bi, ativa)] = (des.bloco(tl[bi]["palavras"], ativa), None)
        img, nome = cache[(bi, ativa)]
        if nome is None:
            nome = salvar(img)
            cache[(bi, ativa)] = (img, nome)
        return nome

    ev = []
    dur_anim = DUR_ANIM[est["animacao"]]
    for bi, b in enumerate(tl):
        t = b["inicio"]
        anim_fim = min(b["inicio"] + dur_anim, b["fim"])
        if dur_anim:
            n = max(1, math.ceil((anim_fim - t) / PASSO_ANIM))
            estado(bi, 0)
            base = cache[(bi, 0 if est["tipo_destaque"] != "nenhum" else None)][0]
            for j in range(n):
                t0 = t + j * PASSO_ANIM
                t1 = min(anim_fim, t0 + PASSO_ANIM)
                if t1 - t0 > 0.001:
                    ev.append((t0, t1, salvar(des.animar(base, (j + 1) / n))))
            t = anim_fim
        for k, (a, z) in enumerate(b["ativos"]):
            a, z = max(a, t), min(z, b["fim"])
            if z - a > 0.001:
                ev.append((a, z, estado(bi, k)))
    return ev, n_img[0]


def _job(video: Path) -> Path:
    """Os dados ficam na pasta do vídeo ORIGINAL: a pasta de entrega (ex.: a dos cortes) fica limpa."""
    reg = saida_registrada(video)
    if reg and reg.get("job") and Path(reg["job"]).exists():
        return Path(reg["job"])
    return pasta_job(video)


def _preparar(video: Path, estilo: str, ajustes: dict, palavras: Path | None, idioma: str):
    video = video.resolve()
    conferir_arquivo_local(video)
    info = info_video(video)
    est = carregar_estilo(estilo, ajustes)
    ws, origem = achar_palavras(video, palavras, idioma)
    if not ws:
        raise CortaErro("Não há palavras para legendar (a transcrição veio vazia).")
    blocos = montar_blocos(ws, est["palavras"])
    tl = linha_do_tempo(blocos, info["duracao"])
    des = Desenhista(est, info["largura"], info["altura"])
    return video, info, est, tl, des, origem


def legendar(video: Path, estilo: str = "creator-bold", ajustes: dict | None = None, palavras: Path | None = None,
             idioma: str = "pt", saida: Path | None = None) -> Path:
    video, info, est, tl, des, origem = _preparar(video, estilo, ajustes or {}, palavras, idioma)
    job = _job(video)
    pasta = job / f"_legenda_{nome_seguro(video.stem)}"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    log(f"== legenda '{est['nome']}' · {len(tl)} blocos · palavras de: {origem}")
    c = Cronometro("desenho da legenda")
    ev, n = _eventos(est, tl, des, pasta)
    Image.new("RGBA", (info["largura"], des.faixa_h), (0, 0, 0, 0)).save(pasta / "vazio.png")
    linhas = ["ffconcat version 1.0"]
    t = 0.0
    for a, z, nome in ev:
        if a - t > 0.001:
            linhas += ["file 'vazio.png'", f"duration {a - t:.4f}"]
        linhas += [f"file '{nome}'", f"duration {z - a:.4f}"]
        t = z
    linhas += ["file 'vazio.png'", f"duration {max(0.04, info['duracao'] - t + 1):.4f}", "file 'vazio.png'"]
    lista = pasta / "lista.ffconcat"
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    c.fim()
    log(f"   {n} imagens")

    perfil = carregar_perfil()
    if saida is None:
        nome = video.stem.replace(" (editado)", "")
        saida = video.with_name(f"{nome} (legendado).mp4")
    saida = saida_livre(Path(saida))
    c = Cronometro("gravação com legenda")
    rodar([ffmpeg(), "-y", "-v", "error", "-i", video, "-f", "concat", "-safe", "0", "-i", lista,
           "-filter_complex", f"[1:v]format=rgba[c];[0:v][c]overlay=x=0:y={des.y_faixa}:shortest=1:format=auto,format=yuv420p[v]",
           "-map", "[v]", "-map", "0:a?", *args_video(perfil), "-c:a", "copy", "-movflags", "+faststart", saida],
          descricao="gravar vídeo com legenda")
    c.fim()
    arq_blocos = job / f"legenda_{nome_seguro(Path(saida).stem)}.json"
    salvar_json(arq_blocos, {"estilo": est, "blocos": tl, "saida": str(saida)})
    reg = saida_registrada(video) or {}
    registrar_saida(job, {"arquivo": str(Path(saida).resolve()), "etapa": "legendar", "estilo": est["id"],
                          "palavras": origem if Path(origem).exists() else None, "mapa": reg.get("mapa"),
                          "origem": str(video), "blocos": str(arq_blocos)})
    shutil.rmtree(pasta, ignore_errors=True)
    log(f"   → {saida}")
    return saida


def previa(video: Path, estilo: str = "creator-bold", ajustes: dict | None = None, palavras: Path | None = None,
           idioma: str = "pt", em: float | None = None) -> Path:
    """3 quadros lado a lado com a legenda aplicada, para aprovar antes de gravar o vídeo inteiro."""
    video, info, est, tl, des, _ = _preparar(video, estilo, ajustes or {}, palavras, idioma)
    job = _job(video)
    if em is not None:
        escolhidos = [min(range(len(tl)), key=lambda i: abs(tl[i]["inicio"] - em))]
    else:
        escolhidos = sorted({0, len(tl) // 2, len(tl) - 1})
    quadros = []
    for bi in escolhidos:
        b = tl[bi]
        k = min(1, len(b["ativos"]) - 1)
        a, z = b["ativos"][k]
        t = (a + z) / 2
        arq = job / f"_quadro_{bi}.png"
        rodar([ffmpeg(), "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", arq], descricao="quadro")
        fundo = Image.open(arq).convert("RGBA")
        fundo.alpha_composite(des.bloco(b["palavras"], k if est["tipo_destaque"] != "nenhum" else None), (0, des.y_faixa))
        quadros.append(fundo)
        arq.unlink(missing_ok=True)
    esc = 0.5 if info["altura"] > info["largura"] else 0.4
    w, h = int(info["largura"] * esc), int(info["altura"] * esc)
    folha = Image.new("RGB", (w * len(quadros) + 20 * (len(quadros) - 1), h), (20, 20, 24))
    for i, q in enumerate(quadros):
        folha.paste(q.convert("RGB").resize((w, h), Image.LANCZOS), (i * (w + 20), 0))
    destino = job / f"previa_{nome_seguro(video.stem)}_{est['id']}.png"
    folha.save(destino)
    log(f"   prévia → {destino}")
    return destino
