"""Formato de saída, enquadramento no rosto e zoom por frase, como filtros do ffmpeg na linha do
tempo da SAÍDA (aplicados na mesma passada da montagem, sem gravar o vídeo de novo).

- formato: original, 9:16, 4:5, 1:1, 16:9.
- enquadrar: rosto (segue o rosto), centro, desfocado (vídeo inteiro sobre fundo desfocado),
  tela-camera (gravação de aula/tutorial: tela em cima, faixa da legenda no meio, câmera embaixo;
  layout aprovado nos 11 shorts da Aula 1).
- zoom: nao, leve, normal, forte. Troca o enquadramento no começo das frases e nos cortes (esconde o
  "pulo" do corte e parece que tem duas câmeras), mais 1 troca no meio de frase longa (> 4,5 s).
  Escalas do "normal" = as validadas nos criativos (1,1 / 1,0 / 1,18 / 1,06 / 1,24 / 1,0), com uma
  "respiração" lenta de 1,5 % dentro de cada plano.
"""
from __future__ import annotations

from .base import CortaErro

FORMATOS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}
ZOOMS = {
    "nao": [1.0],
    "leve": [1.0, 1.06, 1.0, 1.1],
    "normal": [1.1, 1.0, 1.18, 1.06, 1.24, 1.0],
    "forte": [1.15, 1.0, 1.3, 1.1, 1.4, 1.0],
}
RESPIRACAO = 0.015
PLANO_MIN = 1.5      # não troca de enquadramento antes disso
FRASE_LONGA = 4.5
ROSTO_ALTURA = 0.38  # o rosto fica a 38 % do topo (validado nos criativos: 36–38 %)


def _par(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _soma(termos: list[str], base: str = "0") -> str:
    """Soma em árvore (o avaliador do ffmpeg se perde com somas lineares enormes)."""
    if not termos:
        return base
    if len(termos) == 1:
        return termos[0]
    m = len(termos) // 2
    return f"({_soma(termos[:m])}+{_soma(termos[m:])})"


def _degraus(intervalos: list[tuple[float, float, float]], base: float) -> str:
    """Função do tempo que vale v entre a e b (e 'base' fora)."""
    termos = [f"gte(t,{a:.3f})*lt(t,{b:.3f})*{v - base:.4f}" for a, b, v in intervalos if abs(v - base) > 1e-4]
    return f"({base:.4f}+{_soma(termos)})" if termos else f"{base:.4f}"


def planos(palavras: list[dict], pedacos: list[list[float]], duracao: float) -> list[tuple[float, float]]:
    """Onde começa cada plano: começo de frase, cada corte da montagem e meio de frase longa."""
    # 1º os cortes da montagem (trocar o enquadramento ali esconde o "pulo"), depois começos de frase
    inicios: list[float] = []
    for t in sorted({0.0, *(round(a, 3) for a, _ in pedacos)}):
        if t < duracao and (not inicios or t - inicios[-1] >= PLANO_MIN):
            inicios.append(t)
    for i in range(1, len(palavras)):
        ant = palavras[i - 1]["word"].strip()
        t = round(palavras[i]["start"], 3)
        if ant and ant[-1] in ".!?" and t < duracao and all(abs(t - x) >= PLANO_MIN for x in inicios):
            inicios.append(t)
    inicios.sort()
    # plano longo ganha um corte no começo de palavra mais perto do meio
    final = []
    for i, a in enumerate(inicios):
        b = inicios[i + 1] if i + 1 < len(inicios) else duracao
        final.append(a)
        if b - a > FRASE_LONGA:
            meio = (a + b) / 2
            ws = [w["start"] for w in palavras if a + PLANO_MIN <= w["start"] <= b - PLANO_MIN]
            if ws:
                final.append(round(min(ws, key=lambda s: abs(s - meio)), 3))
    return [(a, final[i + 1] if i + 1 < len(final) else duracao) for i, a in enumerate(final)]


FAIXA = 320           # altura da faixa da legenda no layout tela + câmera (em 1920)
COR_FAIXA = "111318"
TELA_MAX, TELA_MIN, CAMERA_MIN = 1000, 540, 560
AMPLIAR_CAMERA = 3.6  # câmera pequena na gravação não estica mais que isso (borra); a sobra vai para a faixa


def _even(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def tela_camera(regioes: dict, ow: int = 1080, oh: int = 1920) -> tuple[str, dict]:
    """Tela em cima (largura toda), faixa escura para a legenda, câmera embaixo enquadrada no rosto."""
    tx, ty, tw, th = regioes["tela"]
    ht = ow * th / tw
    if ht > TELA_MAX:                      # tela "alta" (documento): mostra o topo
        th = _even(tw * TELA_MAX / ow)
        ht = TELA_MAX
    elif ht < TELA_MIN:                    # tela muito larga: corta as laterais, mantém o centro
        nw = _even(th * ow / TELA_MIN)
        tx, tw, ht = tx + (tw - nw) // 2, nw, TELA_MIN
    ht = _even(ht)
    cx, cy, cw, ch = regioes["camera"]
    faixa = FAIXA
    hc = oh - ht - faixa
    if hc < CAMERA_MIN:
        faixa = max(200, oh - ht - CAMERA_MIN)
        hc = oh - ht - faixa
    limite = _even(max(CAMERA_MIN, ch * AMPLIAR_CAMERA))
    if hc > limite:
        faixa += hc - limite
        hc = limite
    fx, fy = regioes.get("rosto", [cx + cw / 2, cy + ch / 2])
    W, H = regioes.get("video", [None, None])
    px = fx * W if W and fx <= 1 else fx
    py = fy * H if H and fy <= 1 else fy
    alvo = ow / hc
    if cw / ch > alvo:                     # câmera mais larga que o espaço: corta as laterais no rosto
        nw = _even(ch * alvo)
        nx = int(min(max(px - nw / 2, cx), cx + cw - nw))
        cam = [nx, cy, nw, _even(ch)]
    else:                                  # mais alta: corta em cima/embaixo, rosto a 40 %
        nh = _even(cw / alvo)
        ny = int(min(max(py - nh * 0.4, cy), cy + ch - nh))
        cam = [cx, ny, _even(cw), nh]
    cadeia = (f",split=2[tc_t][tc_c];[tc_t]crop={_even(tw)}:{_even(th)}:{tx}:{ty},scale={ow}:{ht}:flags=lanczos,"
              f"pad={ow}:{ht + faixa}:0:0:color=0x{COR_FAIXA}[tc_topo];"
              f"[tc_c]crop={cam[2]}:{cam[3]}:{cam[0]}:{cam[1]},scale={ow}:{hc}:flags=lanczos[tc_cam];"
              f"[tc_topo][tc_cam]vstack=inputs=2,setsar=1")
    geo = {"modo": "tela-camera", "ow": ow, "oh": oh, "tela": [tx, ty, _even(tw), _even(th)], "ht": ht, "faixa": faixa,
           "camera": cam, "hc": hc, "cor_faixa": COR_FAIXA, "y_legenda": (ht + faixa / 2) / oh}
    return cadeia, geo


def filtro(largura: int, altura: int, formato: str | None, modo: str, zoom: str,
           planos_saida: list[tuple[float, float]], rosto_por_plano: list[tuple[float, float]],
           regioes: dict | None = None) -> tuple[str, int, int, dict]:
    """Cadeia de filtros (começa com vírgula), o tamanho final e a geometria de cada plano
    (guardada para a conferência refazer o mesmo recorte no quadro original)."""
    if zoom not in ZOOMS:
        raise CortaErro(f"zoom='{zoom}' não existe. Use: {', '.join(ZOOMS)}")
    if modo not in ("rosto", "centro", "desfocado", "tela-camera"):
        raise CortaErro(f"enquadrar='{modo}' não existe. Use: rosto, centro, desfocado ou tela-camera.")
    if formato in (None, "", "original"):
        ow, oh = largura, altura
    elif formato in FORMATOS:
        ow, oh = FORMATOS[formato]
    else:
        raise CortaErro(f"formato='{formato}' não existe. Use: original, {', '.join(FORMATOS)}")
    alvo = ow / oh

    if modo == "tela-camera":
        if not regioes:
            raise CortaErro("O layout tela-camera precisa das regiões (corta regioes VIDEO).")
        if (ow, oh) != (1080, 1920):
            raise CortaErro("O layout tela-camera é vertical: use --formato 9:16.")
        cadeia, geo = tela_camera(regioes, ow, oh)
        return cadeia, ow, oh, geo

    if modo == "desfocado":
        geo = {"modo": "desfocado", "ow": ow, "oh": oh}
        if abs(largura / altura - alvo) < 0.01:
            return f",scale={ow}:{oh}:flags=lanczos,setsar=1", ow, oh, geo
        return (f",split[fundo][frente];[fundo]scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},"
                f"boxblur=30:2,eq=brightness=-0.08[fd];[frente]scale={ow}:{oh}:force_original_aspect_ratio=decrease[fr];"
                f"[fd][fr]overlay=(W-w)/2:(H-h)/2,setsar=1"), ow, oh, geo

    if largura / altura > alvo:
        ch, cw = altura, _par(altura * alvo)
    else:
        cw, ch = largura, _par(largura / alvo)

    escalas = ZOOMS[zoom]
    z_int = []
    for i, (a, b) in enumerate(planos_saida):
        z_int.append((a, b, escalas[i % len(escalas)]))
    tem_zoom = zoom != "nao"
    if tem_zoom:
        termos = []
        for a, b, z in z_int:
            dur = max(0.04, b - a)
            termos.append(f"gte(t,{a:.3f})*lt(t,{b:.3f})*({z:.4f}*(1+{RESPIRACAO}*(t-{a:.3f})/{dur:.3f})-1)")
        Z = f"(1+{_soma(termos)})"
    if modo == "rosto":
        cx = _degraus([(a, b, p[0]) for (a, b), p in zip(planos_saida, rosto_por_plano)], 0.5)
        cy = _degraus([(a, b, p[1]) for (a, b), p in zip(planos_saida, rosto_por_plano)], 0.4)
        yf = ROSTO_ALTURA
    else:
        cx, cy, yf = "0.5", "0.5", 0.5

    cadeia = ""
    if tem_zoom:
        cadeia += f",scale=w='trunc(iw*{Z}/2)*2':h='trunc(ih*{Z}/2)*2':eval=frame:flags=bicubic"
    if (cw, ch) != (largura, altura) or tem_zoom:
        # largura/altura do quadro ampliado calculadas aqui: o crop do ffmpeg guarda o iw/ih do 1º quadro
        # e não acompanha o tamanho que muda a cada quadro (o enquadramento saía deslocado)
        Wz = f"trunc({largura}*{Z}/2)*2" if tem_zoom else str(largura)
        Hz = f"trunc({altura}*{Z}/2)*2" if tem_zoom else str(altura)
        cadeia += (f",crop={cw}:{ch}:x='clip({cx}*{Wz}-{cw}/2,0,{Wz}-{cw})'"
                   f":y='clip({cy}*{Hz}-{ch}*{yf},0,{Hz}-{ch})'")
    if (cw, ch) != (ow, oh):
        cadeia += f",scale={ow}:{oh}:flags=lanczos"
    cadeia += ",setsar=1"
    if modo == "rosto":
        pos = rosto_por_plano
    else:
        pos = [(0.5, 0.5)] * len(planos_saida)
    geo = {"modo": modo, "ow": ow, "oh": oh, "cw": cw, "ch": ch, "yf": yf, "respiracao": RESPIRACAO if tem_zoom else 0.0,
           "planos": [[a, b, z if tem_zoom else 1.0, p[0], p[1]] for (a, b, z), p in zip(z_int, pos)]}
    return cadeia, ow, oh, geo
