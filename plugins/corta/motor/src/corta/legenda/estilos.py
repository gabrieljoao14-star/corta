"""Estilos de legenda: um arquivo JSON por estilo em catalogo/legendas. A receita escolhe um
estilo e muda o que quiser com ajustes (cor, fonte, palavras, posição…)."""
from __future__ import annotations

import re

from ..base import RAIZ_PLUGIN, CortaErro, ler_json, log

PASTA_ESTILOS = RAIZ_PLUGIN / "catalogo" / "legendas"
PASTA_FONTES = RAIZ_PLUGIN / "assets" / "fontes"

# nomes que o app e as pessoas usam → nome do motor
APELIDOS = {
    "letras": {"upper": "maiusculas", "maiúsculas": "maiusculas", "lower": "minusculas", "minúsculas": "minusculas"},
    "animacao": {"pop": "pop", "bounce": "pulo", "fade": "aparecer", "slide": "subir", "none": "nenhuma"},
    "tipo_destaque": {"color": "cor", "box": "caixa", "scale": "escala", "underline": "sublinhado", "none": "nenhum"},
    "posicao": {"bottom": "baixo", "center": "centro", "middle": "centro", "top": "topo", "em cima": "topo", "embaixo": "baixo"},
}
VALORES = {
    "letras": {"maiusculas", "normal", "minusculas"},
    "animacao": {"pop", "pulo", "aparecer", "subir", "nenhuma"},
    "tipo_destaque": {"cor", "caixa", "escala", "sublinhado", "nenhum"},
    "posicao": {"baixo", "centro", "topo"},
}
NUMEROS = {"tamanho": (0.4, 2.5), "contorno": (0, 20), "sombra": (0, 20), "brilho": (0, 30), "palavras": (1, 8),
           "giro_destaque": (-15, 15), "escala_destaque": (1.0, 1.4)}
CORES = {"cor", "destaque", "cor_contorno", "cor_brilho", "fundo_bloco", "cor_texto_caixa"}
# fontes por nome amigável → arquivo
FONTES = {
    "montserrat": "montserrat-900-normal", "montserrat 900": "montserrat-900-normal", "montserrat 800": "montserrat-800-normal",
    "montserrat 700": "montserrat-700-normal", "poppins": "poppins-900-normal", "poppins 900": "poppins-900-normal",
    "poppins 600": "poppins-600-normal", "anton": "anton-400-normal", "bebas neue": "bebas-neue-400-normal",
    "luckiest guy": "luckiest-guy-400-normal", "dm sans": "dm-sans-700-normal", "dm sans 700": "dm-sans-700-normal",
    "dm sans 500": "dm-sans-500-normal", "playfair display": "playfair-display-700-italic", "inter": "inter-600-normal",
}


def nomes_estilos() -> list[str]:
    return sorted(p.stem for p in PASTA_ESTILOS.glob("*.json"))


def _cor(v: str, chave: str) -> str | None:
    if v in (None, "", "nenhum", "nenhuma", "null", "none"):
        return None
    v = v.strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", v):
        return "#" + v.lstrip("#").upper()
    if chave == "cor_texto_caixa" and v == "auto":
        return "auto"
    raise CortaErro(f"Cor '{v}' em {chave} não é válida. Use o formato #RRGGBB, ex.: #FFE14D.")


def carregar_estilo(nome: str, ajustes: dict | None = None) -> dict:
    arq = PASTA_ESTILOS / f"{nome}.json"
    if not arq.exists():
        raise CortaErro(f"Estilo '{nome}' não existe. Estilos: {', '.join(nomes_estilos())}")
    est = ler_json(arq)
    for k, v in (ajustes or {}).items():
        k = k.strip().lower()
        if k == "fonte":
            chave = str(v).strip().lower()
            arquivo = FONTES.get(chave, chave)
            if not (PASTA_FONTES / f"{arquivo}.ttf").exists():
                raise CortaErro(f"Fonte '{v}' não está no plugin. Fontes: {', '.join(sorted(set(FONTES)))}")
            est["fonte"] = arquivo
        elif k in VALORES:
            val = APELIDOS[k].get(str(v).strip().lower(), str(v).strip().lower())
            if val not in VALORES[k]:
                raise CortaErro(f"{k}='{v}' não existe. Use: {', '.join(sorted(VALORES[k]))}")
            est[k] = val
        elif k in NUMEROS:
            lo, hi = NUMEROS[k]
            try:
                num = float(v)
            except ValueError:
                raise CortaErro(f"{k} precisa ser um número (recebi '{v}').")
            est[k] = max(lo, min(hi, int(num) if k == "palavras" else num))
        elif k in CORES:
            est[k] = _cor(str(v), k)
        else:
            raise CortaErro(f"Ajuste '{k}' não existe. Ajustes: fonte, {', '.join(sorted(set(VALORES) | set(NUMEROS) | CORES))}")
    return est


def listar_estilos() -> None:
    for n in nomes_estilos():
        e = ler_json(PASTA_ESTILOS / f"{n}.json")
        log(f"{n:18s} {e['nome']}: {e['descricao']}")
