"""Acabamento por cima da legenda: gancho escrito no topo, chamada (CTA) no final, barra de
progresso e sons nas viradas. Tudo sai na mesma gravação da legenda.

Regras (notas 01 e 06, e a preferência por motion com contenção):
- gancho dentro da zona segura do Reels (nada nos 16 % de cima), lido num relance: até ~10 palavras.
  "pergunta | resposta" vira 2 níveis: pergunta em branco e resposta numa faixa colorida.
  As palavras entram uma a uma (40 ms) com um "pop".
- CTA entra subindo, acima da legenda e fora dos 24 % de baixo (onde fica o botão do Instagram).
- sons: poucos e com motivo. "poucos" = impacto no gancho, pop no CTA e no máximo 3 whooshes nas
  maiores trocas de zoom; "todos" = whoosh em toda troca de plano. Sintetizados por código: sem
  direitos autorais.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .desenho import _contraste, _fonte, _rgb

ESCALONAR = 0.04      # entre uma palavra e a próxima do gancho
POP = 0.15
SUBIR = 0.25
PASSO = 1 / 30


def _y_topo(w: int, h: int) -> float:
    """Onde começa (borda de cima) o gancho: logo abaixo dos 16 % de cima que o Reels cobre."""
    return 0.165 if h > w * 1.5 else (0.12 if h > w else 0.08)


def _y_cta(w: int, h: int) -> float:
    return 0.57 if h > w * 1.5 else (0.62 if h > w else 0.68)


class Camada:
    """Desenha gancho e CTA em imagens do tamanho do quadro (transparentes)."""

    def __init__(self, estilo: dict, largura: int, altura: int):
        self.e, self.W, self.H = estilo, largura, altura
        self.px = max(18, int(round(min(largura, altura) * 0.074 * 0.95)))
        self.fonte = _fonte(estilo["fonte"], self.px)
        self.contorno = max(3, int(round(6 * self.px / 80)))
        self.destaque = estilo["destaque"] if estilo["destaque"].upper() != estilo["cor"].upper() else "#FFE14D"

    def _texto(self, t: str) -> str:
        return t.upper() if self.e["letras"] == "maiusculas" else t

    def _quebrar(self, palavras: list[str], maxw: float) -> list[list[str]]:
        linhas, atual = [], []
        for p in palavras:
            teste = " ".join(atual + [p])
            if atual and self.fonte.getlength(self._texto(teste)) > maxw:
                linhas.append(atual)
                atual = [p]
            else:
                atual.append(p)
        if atual:
            linhas.append(atual)
        return linhas

    def gancho(self, texto: str, t_rel: float | None = None) -> Image.Image:
        """t_rel = tempo desde o começo do gancho (None = todas as palavras já entraram).
        A palavra k entra em k × 40 ms e cresce em 150 ms."""
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        partes = [p.strip() for p in texto.split("|") if p.strip()]
        niveis = [(partes[0], "solto")] + ([(partes[1], "faixa")] if len(partes) > 1 else [])
        if len(partes) == 1:
            niveis = [(partes[0], "faixa_escura")]
        maxw = self.W * 0.82
        linhas = []
        for txt, tipo in niveis:
            for l in self._quebrar(txt.split(), maxw):
                linhas.append((l, tipo))
        alt = int(self.px * 1.35)
        y = int(self.H * _y_topo(self.W, self.H))
        k = 0
        asc, desc = self.fonte.getmetrics()
        for palavras, tipo in linhas:
            frase = self._texto(" ".join(palavras))
            lw = self.fonte.getlength(frase)
            x0 = (self.W - lw) / 2
            base = y + asc
            mostrar = []
            for p in palavras:
                prog = 1.0 if t_rel is None else (t_rel - k * ESCALONAR) / POP
                k += 1
                if prog > 0:
                    mostrar.append((p, min(1.0, prog)))
            if mostrar and tipo in ("faixa", "faixa_escura"):
                d = ImageDraw.Draw(img)
                cor = self.destaque if tipo == "faixa" else "#000000"
                alfa = 255 if tipo == "faixa" else 175
                parcial = self.fonte.getlength(self._texto(" ".join(p for p, _ in mostrar)))
                pad_x, pad_y = int(self.px * 0.28), int(self.px * 0.14)
                d.rounded_rectangle((x0 - pad_x, base - asc - pad_y + int(self.px * 0.08), x0 + parcial + pad_x, base + desc + pad_y - int(self.px * 0.08)),
                                    radius=int(self.px * 0.22), fill=_rgb(cor, alfa))
            x = x0
            for p, prog in mostrar:
                t = self._texto(p)
                pw = self.fonte.getlength(t)
                if tipo == "faixa":
                    cor_txt, sw = _contraste(self.destaque), 0
                elif tipo == "faixa_escura":
                    cor_txt, sw = "#FFFFFF", 0
                else:
                    cor_txt, sw = "#FFFFFF", self.contorno
                esc = 0.6 + 0.4 * (1 - (1 - prog) ** 3) if prog < 1 else 1.0
                pad = sw + 6
                camada = Image.new("RGBA", (int(pw) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
                ImageDraw.Draw(camada).text((pad, pad + asc), t, font=self.fonte, fill=_rgb(cor_txt), anchor="ls",
                                            stroke_width=sw, stroke_fill=(0, 0, 0, 255) if sw else None)
                if esc != 1.0:
                    camada = camada.resize((max(1, int(camada.width * esc)), max(1, int(camada.height * esc))), Image.BILINEAR)
                cx, cy = x + pw / 2, base - (asc - desc) / 2
                img.alpha_composite(camada, (int(cx - camada.width / 2), int(cy - camada.height / 2)))
                x += pw + self.fonte.getlength(" ")
            y += alt
        return img

    def cta(self, texto: str, prog: float) -> Image.Image:
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        f = self.fonte
        seta = "  ↓" if f.getmask("↓").getbbox() is not None else ""
        bruto = self._texto(texto.strip())
        maxw = self.W * 0.8
        linhas = [bruto + seta]
        if f.getlength(linhas[0]) > maxw:
            if "·" in bruto:
                a, b = [x.strip() for x in bruto.split("·", 1)]
                linhas = [a, b + seta]
            else:
                ps = bruto.split()
                k = min(range(1, len(ps)), key=lambda i: abs(f.getlength(" ".join(ps[:i])) - f.getlength(" ".join(ps[i:]))),
                        default=1)
                linhas = [" ".join(ps[:k]), " ".join(ps[k:]) + seta]
        while max(f.getlength(l) for l in linhas) > maxw and f.size > 18:
            f = _fonte(self.e["fonte"], int(f.size * 0.92))
        asc, desc = f.getmetrics()
        alt = int(f.size * 1.2)
        larg = max(f.getlength(l) for l in linhas)
        p = max(0.0, min(1.0, prog))
        e = 1 - (1 - p) ** 3
        dy = int((1 - e) * self.px * 0.8)
        alfa = int(255 * min(1.0, p * 2))
        yc = int(self.H * _y_cta(self.W, self.H)) + dy
        topo = yc - (alt * len(linhas)) // 2
        pad_x, pad_y = int(self.px * 0.45), int(self.px * 0.28)
        caixa = (int((self.W - larg) / 2) - pad_x, topo - pad_y, int((self.W + larg) / 2) + pad_x, topo + alt * len(linhas) + pad_y)
        camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        raio = (caixa[3] - caixa[1]) // 2 if len(linhas) == 1 else int(self.px * 0.4)
        d.rounded_rectangle(caixa, radius=raio, fill=_rgb(self.destaque))
        for i, l in enumerate(linhas):
            base = topo + i * alt + (alt + asc - desc) // 2
            d.text(((self.W - f.getlength(l)) / 2, base), l, font=f, fill=_rgb(_contraste(self.destaque)), anchor="ls")
        if alfa < 255:
            camada.putalpha(camada.getchannel("A").point(lambda v: v * alfa // 255))
        img.alpha_composite(camada)
        return img


def eventos(camada: Camada, pasta: Path, duracao: float, gancho: str | None, gancho_ate: float,
            cta: str | None, cta_em: float | None) -> list[tuple[float, float, str]]:
    ev, n = [], [0]

    def salvar(img):
        nome = f"t{n[0]:04d}.png"
        img.save(pasta / nome, compress_level=1)
        n[0] += 1
        return nome

    if gancho:
        total = len(gancho.replace("|", " ").split())
        entrada = total * ESCALONAR + POP
        t = 0.0
        while t < entrada and t < gancho_ate:
            ev.append((t, min(t + PASSO, gancho_ate), salvar(camada.gancho(gancho, t + PASSO))))
            t += PASSO
        cheio = camada.gancho(gancho)
        ev.append((t, max(t, gancho_ate - 0.2), salvar(cheio)))
        for j in range(6):  # some em 0,2 s
            a = gancho_ate - 0.2 + j * 0.2 / 6
            img = cheio.copy()
            img.putalpha(img.getchannel("A").point(lambda v, f=1 - (j + 1) / 6: int(v * f)))
            ev.append((a, a + 0.2 / 6, salvar(img)))
    if cta:
        ini = cta_em if cta_em is not None else max(0.0, duracao - 4.0)
        ini = max(ini, ev[-1][1] if ev else 0.0)
        t = ini
        while t < ini + SUBIR:
            ev.append((t, t + PASSO, salvar(camada.cta(cta, (t - ini + PASSO) / SUBIR))))
            t += PASSO
        ev.append((t, duracao + 1, salvar(camada.cta(cta, 1.0))))
    return [(a, b, nome) for a, b, nome in ev if b - a > 0.001]


# ---------------- sons ----------------
SR = 48000


def _env(n: int, ataque: float, queda: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(ataque, 1e-4)) * np.exp(-t / queda)


def som(nome: str) -> np.ndarray:
    rng = np.random.default_rng(7)
    if nome == "whoosh":
        n = int(0.38 * SR)
        ruido = rng.standard_normal(n)
        t = np.arange(n) / n
        corte = 400 + 3200 * np.sin(np.pi * t) ** 2          # o filtro abre e fecha: "fuuush"
        y, a = np.zeros(n), 0.0
        for i in range(n):
            k = 1 - math.exp(-2 * math.pi * corte[i] / SR)
            a += k * (ruido[i] - a)
            y[i] = a
        y *= np.sin(np.pi * t) ** 2
        pico = 10 ** (-20 / 20)
    elif nome == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        freq = 400 + 500 * np.exp(-t / 0.02)
        y = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(n, 0.002, 0.03)
        pico = 10 ** (-16 / 20)
    elif nome == "impacto":
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        freq = 40 + 50 * np.exp(-t / 0.05)
        grave = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(n, 0.003, 0.18)
        ruido = rng.standard_normal(n) * _env(n, 0.001, 0.02) * 0.3
        y = grave + ruido
        pico = 10 ** (-14 / 20)
    else:
        raise ValueError(nome)
    return (y / (np.abs(y).max() + 1e-9) * pico).astype(np.float32)


def viradas(planos: list[list[float]], modo: str, maximo: int = 3) -> list[float]:
    """Momentos de whoosh: trocas de plano (as maiores mudanças de zoom, se 'poucos')."""
    if modo == "nao" or not planos or len(planos) < 2:
        return []
    trocas = [(abs(planos[i][2] - planos[i - 1][2]), planos[i][0]) for i in range(1, len(planos))]
    if modo == "todos":
        return [t for _, t in trocas]
    escolhidas = []
    for dz, t in sorted(trocas, reverse=True):
        if dz < 0.1 or len(escolhidas) >= maximo:
            break
        if all(abs(t - x) >= 6 for x in escolhidas):
            escolhidas.append(t)
    return sorted(escolhidas)


def faixa_de_sons(duracao: float, pontos: list[tuple[float, str]], destino: Path) -> Path:
    import soundfile as sf
    total = np.zeros(int((duracao + 1) * SR), np.float32)
    for t, nome in pontos:
        s = som(nome)
        i = int(max(0.0, t - (0.19 if nome == "whoosh" else 0.0)) * SR)   # o meio do whoosh cai no corte
        j = min(len(total), i + len(s))
        total[i:j] += s[: j - i]
    sf.write(destino, np.stack([total, total], 1), SR, subtype="PCM_16")
    return destino
