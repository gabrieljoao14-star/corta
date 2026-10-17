"""Comandos do motor. O Claude chama estes comandos; a pessoa normalmente nem vê.

  corta perfil [--recalcular]
  corta preparar VIDEO [--voz leve|forte|nao] [--ritmo rapido|natural]
  corta transcrever VIDEO [--idioma pt] [--modelo large-v2]
  corta trechos VIDEO [--isolado auto|todos|nenhum]
  corta montar VIDEO [--takes takes.json] [--apertar|--sem-apertar] [--saida ARQ]
  corta legendar VIDEO [--estilo creator-bold] [--ajuste chave=valor …] [--saida ARQ]
  corta previa VIDEO [--estilo …] [--em SEGUNDOS]
  corta corrigir VIDEO lerite=holerite ["lei rite=holerite" …]
  corta estilos
  corta verificar SAIDA
  corta amostra
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .base import CortaErro, configurar_saida_utf8, log


def _ajustes(lista):
    out = {}
    for item in lista or []:
        if "=" not in item:
            raise CortaErro(f"Ajuste '{item}' precisa ser chave=valor (ex.: cor=#FFFFFF).")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main(argv=None):
    configurar_saida_utf8()
    ap = argparse.ArgumentParser(prog="corta", description="Motor de edição do /corta")
    ap.add_argument("--version", action="version", version=f"corta {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("perfil", help="mede o computador e escolhe as configurações")
    p.add_argument("--recalcular", action="store_true")

    p = sub.add_parser("preparar", help="voz limpa + onde tem fala")
    p.add_argument("video", type=Path)
    p.add_argument("--voz", default=None, choices=["leve", "forte", "nao"])
    p.add_argument("--ritmo", default="rapido", choices=["rapido", "natural"])

    p = sub.add_parser("transcrever", help="transcrição literal por palavra")
    p.add_argument("video", type=Path)
    p.add_argument("--idioma", default="pt")
    p.add_argument("--modelo", default=None)

    p = sub.add_parser("trechos", help="lista numerada dos trechos com o texto")
    p.add_argument("video", type=Path)
    p.add_argument("--isolado", default="auto", choices=["auto", "todos", "nenhum"])
    p.add_argument("--idioma", default="pt")

    p = sub.add_parser("montar", help="monta o vídeo só com o que fica")
    p.add_argument("video", type=Path)
    p.add_argument("--takes", type=Path)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apertar", dest="apertar", action="store_true", default=None)
    g.add_argument("--sem-apertar", dest="apertar", action="store_false")
    p.add_argument("--saida", type=Path)

    for nome in ("legendar", "previa"):
        p = sub.add_parser(nome, help="queima a legenda" if nome == "legendar" else "quadro de prévia da legenda")
        p.add_argument("video", type=Path)
        p.add_argument("--estilo", default="creator-bold")
        p.add_argument("--ajuste", action="append", metavar="CHAVE=VALOR")
        p.add_argument("--palavras", type=Path, help="palavras com tempo (padrão: as da montagem)")
        p.add_argument("--idioma", default="pt")
        if nome == "legendar":
            p.add_argument("--saida", type=Path)
        else:
            p.add_argument("--em", type=float, default=None, help="segundo do vídeo (padrão: meio da 1ª frase)")

    p = sub.add_parser("corrigir", help="corrige palavras erradas da transcrição (errado=certo)")
    p.add_argument("video", type=Path)
    p.add_argument("correcoes", nargs="+", metavar="ERRADO=CERTO")

    sub.add_parser("estilos", help="lista os estilos de legenda")

    p = sub.add_parser("verificar", help="confere a saída (duração, sincronia, fala removida, legenda)")
    p.add_argument("saida", type=Path)

    sub.add_parser("amostra", help="edita o vídeo de amostra e confere (teste da instalação)")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "perfil":
            from .perfil import carregar, mostrar
            mostrar(carregar(recalcular=a.recalcular))
        elif a.cmd == "preparar":
            from .perfil import carregar
            from .preparar import preparar
            preparar(a.video, voz=a.voz or carregar()["voz_padrao"], ritmo=a.ritmo)
        elif a.cmd == "transcrever":
            from .transcrever import transcrever
            transcrever(a.video, idioma=a.idioma, nome_modelo=a.modelo)
        elif a.cmd == "trechos":
            from .trechos import listar
            listar(a.video, isolado=a.isolado, idioma=a.idioma)
        elif a.cmd == "montar":
            from .montar import montar
            montar(a.video, takes=a.takes, apertar=a.apertar, saida=a.saida)
        elif a.cmd == "legendar":
            from .legenda.queimar import legendar
            legendar(a.video, estilo=a.estilo, ajustes=_ajustes(a.ajuste), palavras=a.palavras, idioma=a.idioma, saida=a.saida)
        elif a.cmd == "previa":
            from .legenda.queimar import previa
            previa(a.video, estilo=a.estilo, ajustes=_ajustes(a.ajuste), palavras=a.palavras, idioma=a.idioma, em=a.em)
        elif a.cmd == "corrigir":
            from .corrigir import corrigir
            corrigir(a.video, a.correcoes)
        elif a.cmd == "estilos":
            from .legenda.estilos import listar_estilos
            listar_estilos()
        elif a.cmd == "verificar":
            from .verificar import verificar
            ok = verificar(a.saida)
            sys.exit(0 if ok else 2)
        elif a.cmd == "amostra":
            from .amostra import amostra
            sys.exit(0 if amostra() else 2)
    except CortaErro as e:
        log(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
