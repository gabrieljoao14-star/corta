"""Desenha cada estado da legenda (bloco + palavra ativa + quadro da animação) numa imagem
transparente do tamanho de uma faixa do vídeo."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .estilos import PASTA_FONTES

REF = 80.0          # tamanho de referência (px numa tela de 1080): contorno, sombra e brilho escalam com ele
MARGEM_LARGURA = 0.86


def _rgb(hexcor: str, alfa: int = 255):
    h = hexcor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alfa)


def _contraste(hexcor: str) -> str:
    r, g, b, _ = _rgb(hexcor)
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


@lru_cache(maxsize=32)
def _fonte(nome: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(PASTA_FONTES / f"{nome}.ttf"), px)


class Desenhista:
    def __init__(self, estilo: dict, largura: int, altura: int):
        self.e, self.W, self.H = estilo, largura, altura
        n = estilo["palavras"]
        fator = {1: 1.6, 2: 1.25, 3: 1.0, 4: 0.9}.get(n, 0.8)
        self.px = max(18, int(round(min(largura, altura) * 0.074 * estilo["tamanho"] * fator)))
        self.k = self.px / REF
        self.fonte = _fonte(estilo["fonte"], self.px)
        self.contorno = int(round(estilo["contorno"] * self.k))
        extra = 0.0
        if estilo["tipo_destaque"] == "caixa":
            extra = 0.34                                  # a caixa não encosta na vizinha
        elif estilo["tipo_destaque"] == "escala":
            extra = (estilo["escala_destaque"] - 1) * 1.2  # palavra maior não encosta ("masnão")
        self.espaco = int(self.px * (0.28 + extra))
        self.alt_linha = int(self.px * 1.22)
        self.faixa_h = int(self.px * 4.6)
        pos = estilo["posicao"]
        vertical = altura > largura
        if pos == "topo":
            yc = 0.22 if vertical else 0.14
        elif pos == "centro":
            yc = 0.5
        else:
            # zona segura do Reels/Stories: nada nos 24 % de baixo
            yc = 0.70 if vertical else (0.86 if largura / altura > 1.5 else 0.80)
        self.y_centro = int(altura * yc)
        self.y_faixa = max(0, min(altura - self.faixa_h, self.y_centro - self.faixa_h // 2))

    # ---------- texto ----------
    def texto(self, w: str) -> str:
        l = self.e["letras"]
        return w.upper() if l == "maiusculas" else w.lower() if l == "minusculas" else w

    def largura_palavra(self, w: str) -> int:
        return int(self.fonte.getlength(self.texto(w))) + 2 * self.contorno

    def quebrar_linhas(self, palavras: list[str]) -> list[list[int]]:
        """Uma linha se couber; senão divide em 2 linhas equilibradas (nada de palavra sozinha
        no meio); só vai para 3+ linhas se 2 não couberem."""
        maxw = self.W * MARGEM_LARGURA
        lw = [self.largura_palavra(w) for w in palavras]
        larg = lambda a, b: sum(lw[a:b]) + self.espaco * (b - a - 1)
        n = len(palavras)
        if larg(0, n) <= maxw or n == 1:
            return [list(range(n))]
        melhor = min(range(1, n), key=lambda k: max(larg(0, k), larg(k, n)))
        if max(larg(0, melhor), larg(melhor, n)) <= maxw:
            return [list(range(melhor)), list(range(melhor, n))]
        linhas, atual, larg = [], [], 0
        for i, w in enumerate(palavras):
            lw = self.largura_palavra(w)
            novo = lw if not atual else larg + self.espaco + lw
            if atual and novo > maxw:
                linhas.append(atual)
                atual, larg = [i], lw
            else:
                atual.append(i)
                larg = novo
        if atual:
            linhas.append(atual)
        return linhas

    # ---------- uma palavra ----------
    def _palavra(self, w: str, ativa: bool) -> tuple[Image.Image, int]:
        """Imagem da palavra e o deslocamento da linha de base dentro dela."""
        e = self.e
        t = self.texto(w)
        f = self.fonte
        tipo = e["tipo_destaque"] if ativa else "nenhum"
        cor = e["destaque"] if tipo in ("cor", "escala") else e["cor"]
        sw = 0 if tipo == "caixa" else self.contorno
        brilho = int(e["brilho"] * self.k)
        sombra = int(e["sombra"] * self.k)
        pad = max(sw, brilho * 2, sombra * 2, int(self.px * 0.2)) + 4
        asc, desc = f.getmetrics()
        larg = int(f.getlength(t)) + 2 * pad
        alt = asc + desc + 2 * pad
        img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        base = pad + asc
        x0 = pad
        if sombra:
            s = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(s).text((x0, base + int(self.px * 0.05)), t, font=f, fill=(0, 0, 0, 190), anchor="ls",
                                   stroke_width=sw, stroke_fill=(0, 0, 0, 190))
            img = Image.alpha_composite(img, s.filter(ImageFilter.GaussianBlur(sombra)))
        if brilho:
            g = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(g).text((x0, base), t, font=f, fill=_rgb(e["cor_brilho"] or e["destaque"]), anchor="ls",
                                   stroke_width=max(2, brilho // 3), stroke_fill=_rgb(e["cor_brilho"] or e["destaque"]))
            g = g.filter(ImageFilter.GaussianBlur(brilho))
            img = Image.alpha_composite(img, g)
            img = Image.alpha_composite(img, g)
        d = ImageDraw.Draw(img)
        if tipo == "caixa":
            l, tp, r, b = d.textbbox((x0, base), t, font=f, anchor="ls")
            px, py = int(self.px * 0.16), int(self.px * 0.10)
            d.rounded_rectangle((l - px, tp - py, r + px, b + py), radius=int(self.px * 0.2), fill=_rgb(e["destaque"]))
            ctx = e["cor_texto_caixa"]
            cor = _contraste(e["destaque"]) if ctx in (None, "auto") else ctx
        d.text((x0, base), t, font=f, fill=_rgb(cor), anchor="ls",
               stroke_width=sw, stroke_fill=_rgb(e["cor_contorno"]) if sw else None)
        if tipo == "sublinhado":
            l, _, r, _ = d.textbbox((x0, base), t, font=f, anchor="ls")
            y = base + int(self.px * 0.14)
            d.rounded_rectangle((l, y, r, y + max(3, int(self.px * 0.08))), radius=3, fill=_rgb(e["destaque"]))
        if tipo == "escala":
            esc = e["escala_destaque"]
            if esc != 1.0:
                img = img.resize((int(img.width * esc), int(img.height * esc)), Image.LANCZOS)
                base = int(base * esc)
            if e["giro_destaque"]:
                cx, cy = img.width / 2, img.height / 2
                img = img.rotate(-e["giro_destaque"], resample=Image.BICUBIC, expand=False, center=(cx, cy))
        return img, base

    # ---------- bloco ----------
    def bloco(self, palavras: list[str], ativa: int | None) -> Image.Image:
        e = self.e
        faixa = Image.new("RGBA", (self.W, self.faixa_h), (0, 0, 0, 0))
        linhas = self.quebrar_linhas(palavras)
        total_h = len(linhas) * self.alt_linha
        asc, desc = self.fonte.getmetrics()
        y_base0 = (self.faixa_h - total_h) // 2 + int(self.alt_linha * 0.5) + (asc - desc) // 2
        d = ImageDraw.Draw(faixa)
        for li, idxs in enumerate(linhas):
            larguras = [self.largura_palavra(palavras[i]) for i in idxs]
            total_w = sum(larguras) + self.espaco * (len(idxs) - 1)
            x = (self.W - total_w) // 2
            y_base = y_base0 + li * self.alt_linha
            if e["fundo_bloco"]:
                px, py = int(self.px * 0.3), int(self.px * 0.16)
                d.rounded_rectangle((x - px, y_base - asc - py + int(self.px * 0.1), x + total_w + px, y_base + desc + py - int(self.px * 0.1)),
                                    radius=int(self.px * 0.22), fill=_rgb(e["fundo_bloco"]))
            for i, lw in zip(idxs, larguras):
                img, base = self._palavra(palavras[i], ativa == i)
                cx = x + lw // 2
                faixa.alpha_composite(img, (int(cx - img.width / 2), int(y_base - base)))
                x += lw + self.espaco
        return faixa

    def animar(self, faixa: Image.Image, prog: float) -> Image.Image:
        """Quadro da animação de entrada do bloco (prog de 0 a 1)."""
        an = self.e["animacao"]
        if an == "nenhuma" or prog >= 1:
            return faixa
        p = max(0.0, min(1.0, prog))
        saida = Image.new("RGBA", faixa.size, (0, 0, 0, 0))
        if an in ("pop", "pulo"):
            if an == "pop":
                esc = 0.6 + 0.4 * (1 - (1 - p) ** 3)
            else:
                c1, c3 = 1.9, 2.9
                esc = 0.4 + 0.6 * (1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2)
            w, h = max(1, int(faixa.width * esc)), max(1, int(faixa.height * esc))
            r = faixa.resize((w, h), Image.BILINEAR)
            saida.alpha_composite(r, ((faixa.width - w) // 2, (faixa.height - h) // 2))
            return saida
        alfa = 1 - (1 - p) ** 2
        img = faixa.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alfa)))
        dy = int((1 - alfa) * self.px * 0.45) if an == "subir" else 0
        if dy:
            img = img.crop((0, 0, faixa.width, faixa.height - dy))
        saida.alpha_composite(img, (0, dy))
        return saida
