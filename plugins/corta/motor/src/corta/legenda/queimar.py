"""Queima a legenda no vídeo: desenha cada estado (bloco + palavra ativa + animação) como imagem,
monta uma lista com a duração de cada uma e cola por cima do vídeo com o ffmpeg numa passada.

As palavras vêm, em ordem de preferência: --palavras; a montagem que gerou este vídeo
(tempos já remapeados); a transcrição deste próprio vídeo.
"""
from __future__ import annotations

import math
import os
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


def _lista_concat(pasta: Path, ev, duracao: float, vazio: str) -> Path:
    linhas = ["ffconcat version 1.0"]
    t = 0.0
    for a, z, nome in ev:
        if a - t > 0.001:
            linhas += [f"file '{vazio}'", f"duration {a - t:.4f}"]
        linhas += [f"file '{nome}'", f"duration {z - max(a, t):.4f}"]
        t = z
    linhas += [f"file '{vazio}'", f"duration {max(0.04, duracao - t + 1):.4f}", f"file '{vazio}'"]
    lista = pasta / f"lista_{vazio.split('.')[0]}.ffconcat"
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return lista


def _juntar(intervalos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(intervalos):
        if out and a <= out[-1][1] + 0.05:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _fim_primeira_frase(tl: list[dict], padrao: float = 3.5) -> float:
    """Onde o gancho sai: fim da 1ª pergunta se ela vier cedo; senão 3,5 s (entre 2,5 e 4,5 s)."""
    for b in tl:
        if b["inicio"] > 4.5:
            break
        if b["palavras"] and b["palavras"][-1].endswith("?"):
            return b["fim"]
    return padrao


def legendar(video: Path, estilo: str = "creator-bold", ajustes: dict | None = None, palavras: Path | None = None,
             idioma: str = "pt", saida: Path | None = None, gancho: str | None = None, gancho_ate: float | None = None,
             cta: str | None = None, cta_em: float | None = None, barra: bool = False, sons: str = "nao") -> Path:
    from .extras import Camada, eventos as eventos_topo, faixa_de_sons, viradas
    sem_legenda = estilo in ("nenhuma", "nenhum", "sem")
    video, info, est, tl, des, origem = _preparar(video, "creator-bold" if sem_legenda else estilo, ajustes or {}, palavras, idioma)
    job = _job(video)
    pasta = job / f"_legenda_{nome_seguro(video.stem)}"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    W, H, dur = info["largura"], info["altura"], info["duracao"]
    if gancho and gancho_ate is None:
        gancho_ate = min(4.5, max(2.5, _fim_primeira_frase(tl)))
    partes = ["sem legenda" if sem_legenda else f"legenda '{est['nome']}'"]
    partes += [nome for nome, ligado in (("gancho", gancho), ("CTA", cta), ("barra", barra)) if ligado]
    if sons != "nao":
        partes.append(f"sons {sons}")
    log(f"== {' · '.join(partes)} · palavras de: {origem}")
    c = Cronometro("desenho")
    entradas, filtros, rotulo = [], [], "[0:v]"
    if not sem_legenda:
        ev, n = _eventos(est, tl, des, pasta)
        if gancho and est["posicao"] == "topo":
            ev = [(a, z, nm) for a, z, nm in ev if a >= gancho_ate]   # legenda no topo espera o gancho sair
        Image.new("RGBA", (W, des.faixa_h), (0, 0, 0, 0)).save(pasta / "vazio.png")
        entradas += ["-f", "concat", "-safe", "0", "-i", _lista_concat(pasta, ev, dur, "vazio.png")]
        filtros.append(f"[1:v]format=rgba[leg];{rotulo}[leg]overlay=x=0:y={des.y_faixa}:shortest=1:format=auto[v1]")
        rotulo = "[v1]"
        log(f"   legenda: {n} imagens")
    camada = Camada(est, W, H)
    cta_ini = None
    if gancho or cta:
        ev_topo = eventos_topo(camada, pasta, dur, gancho, gancho_ate or 0.0, cta, cta_em)
        if cta:
            cta_ini = cta_em if cta_em is not None else max(0.0, dur - 4.0)
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(pasta / "vazio_topo.png")
        entradas += ["-f", "concat", "-safe", "0", "-i", _lista_concat(pasta, ev_topo, dur, "vazio_topo.png")]
        idx = 1 + (0 if sem_legenda else 1)
        # a camada cobre a tela inteira: só mistura nos momentos do gancho e do CTA (o resto passa direto)
        janelas = [f"between(t,{a:.3f},{b:.3f})" for a, b in _juntar([(a, z) for a, z, _ in ev_topo])]
        quando = "+".join(janelas) or "0"
        filtros.append(f"[{idx}:v]format=rgba[topo];{rotulo}[topo]overlay=0:0:shortest=1:format=auto:enable='{quando}'[v2]")
        rotulo = "[v2]"
        log(f"   gancho/CTA: {len(ev_topo)} imagens")
    if barra:
        from ..base import fps_saida
        bh = max(6, int(H * 0.006))
        F = fps_saida(info["fps"])
        filtros.append(f"{rotulo}drawbox=x=0:y=0:w=iw:h={bh}:color=black@0.35:t=fill[vb];"
                       f"color=c=0x{camada.destaque.lstrip('#')}:s={W}x{bh}:r={F}[bar];"
                       f"[vb][bar]overlay=x='-w+w*t/{dur:.3f}':y=0:shortest=1[v3]")
        rotulo = "[v3]"
    filtros.append(f"{rotulo}format=yuv420p[v]")
    audio = ["-map", "0:a?", "-c:a", "copy"]
    pontos = []
    if sons != "nao":
        if gancho:
            pontos.append((0.0, "impacto"))
        if cta:
            pontos.append((cta_ini, "pop"))
        reg = saida_registrada(video) or {}
        planos = []
        if reg.get("mapa") and Path(reg["mapa"]).exists():
            geo = ler_json(reg["mapa"]).get("quadro") or {}
            planos = geo.get("planos", [])
        for t in viradas(planos, sons):
            if (not gancho or t > (gancho_ate or 0) + 0.5) and (cta_ini is None or abs(t - cta_ini) > 1):
                pontos.append((t, "whoosh"))
        if pontos:
            arq_sons = faixa_de_sons(dur, pontos, pasta / "sons.wav")
            entradas += ["-i", arq_sons]
            idx = 1 + (0 if sem_legenda else 1) + (1 if (gancho or cta) else 0)
            filtros.append(f"[0:a][{idx}:a]amix=inputs=2:normalize=0:duration=first[a]")
            audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
            log(f"   sons: {', '.join(f'{nm} em {t:.1f} s' for t, nm in sorted(pontos))}")
    c.fim()

    perfil = carregar_perfil()
    if saida is None:
        nome = video.stem.replace(" (editado)", "")
        saida = video.with_name(f"{nome} ({'final' if sem_legenda else 'legendado'}).mp4")
    saida = saida_livre(Path(saida))
    grafo = pasta / "filtros.txt"
    grafo.write_text(";".join(filtros), encoding="utf-8")
    c = Cronometro("gravação")
    rodar([ffmpeg(), "-y", "-v", "error", "-i", video, *entradas, "-/filter_complex", grafo,
           "-map", "[v]", *audio, *args_video(perfil), "-movflags", "+faststart", saida],
          descricao="gravar vídeo com legenda")
    c.fim()
    arq_blocos = job / f"legenda_{nome_seguro(Path(saida).stem)}.json"
    salvar_json(arq_blocos, {"estilo": None if sem_legenda else est, "blocos": [] if sem_legenda else tl, "saida": str(saida),
                             "gancho": gancho, "gancho_ate": gancho_ate, "cta": cta, "cta_em": cta_ini, "barra": barra,
                             "sons": sorted(pontos)})
    reg = saida_registrada(video) or {}
    registrar_saida(job, {"arquivo": str(Path(saida).resolve()), "etapa": "legendar", "estilo": None if sem_legenda else est["id"],
                          "palavras": origem if Path(origem).exists() else None, "mapa": reg.get("mapa"),
                          "origem": str(video), "blocos": str(arq_blocos)})
    if not os.environ.get("CORTA_MANTER"):          # CORTA_MANTER=1 guarda as imagens para diagnóstico
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
