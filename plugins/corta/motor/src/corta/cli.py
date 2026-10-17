"""Comandos do motor. O Claude chama estes comandos; a pessoa normalmente nem vê.

  corta perfil [--recalcular]
  corta preparar VIDEO [--voz leve|forte|nao] [--ritmo rapido|natural]
  corta transcrever VIDEO [--idioma pt] [--modelo large-v2]
  corta trechos VIDEO [--isolado auto|todos|nenhum]
  corta montar VIDEO [--takes takes.json] [--apertar|--sem-apertar] [--saida ARQ]
               [--formato 9:16] [--enquadrar rosto|centro|desfocado] [--zoom nao|leve|normal|forte]
  corta legendar VIDEO [--estilo creator-bold|nenhuma] [--ajuste chave=valor …] [--saida ARQ]
                 [--gancho "pergunta | resposta"] [--cta "Toque em Saiba mais"] [--barra] [--sons poucos]
  corta previa VIDEO [--estilo …] [--em SEGUNDOS]
  corta corrigir VIDEO lerite=holerite ["lei rite=holerite" …]
  corta texto VIDEO
  corta cortar VIDEO --cortes cortes.json [--formato 9:16] [--enquadrar rosto] [--zoom leve] [--legenda ESTILO]
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
    p.add_argument("--formato", default=None, choices=["original", "9:16", "4:5", "1:1", "16:9"])
    p.add_argument("--enquadrar", default="rosto", choices=["rosto", "centro", "desfocado"])
    p.add_argument("--zoom", default="nao", choices=["nao", "leve", "normal", "forte"])

    for nome in ("legendar", "previa"):
        p = sub.add_parser(nome, help="queima a legenda" if nome == "legendar" else "quadro de prévia da legenda")
        p.add_argument("video", type=Path)
        p.add_argument("--estilo", default="creator-bold")
        p.add_argument("--ajuste", action="append", metavar="CHAVE=VALOR")
        p.add_argument("--palavras", type=Path, help="palavras com tempo (padrão: as da montagem)")
        p.add_argument("--idioma", default="pt")
        if nome == "legendar":
            p.add_argument("--saida", type=Path)
            p.add_argument("--gancho", default=None, help='texto no topo; "pergunta | resposta" faz 2 níveis')
            p.add_argument("--gancho-ate", type=float, default=None, help="segundo em que o gancho sai (padrão: fim da 1ª frase)")
            p.add_argument("--cta", default=None, help='chamada no final, ex.: "Toque em Saiba mais"')
            p.add_argument("--cta-em", type=float, default=None, help="segundo em que a chamada entra (padrão: 4 s antes do fim)")
            p.add_argument("--barra", action="store_true", help="barra de progresso no topo")
            p.add_argument("--sons", default="nao", choices=["nao", "poucos", "todos"])
        else:
            p.add_argument("--em", type=float, default=None, help="segundo do vídeo (padrão: meio da 1ª frase)")

    p = sub.add_parser("corrigir", help="corrige palavras erradas da transcrição (errado=certo)")
    p.add_argument("video", type=Path)
    p.add_argument("correcoes", nargs="+", metavar="ERRADO=CERTO")

    p = sub.add_parser("texto", help="transcrição em frases com o tempo (para escolher cortes)")
    p.add_argument("video", type=Path)

    p = sub.add_parser("cortar", help="gera os cortes de um vídeo longo a partir de cortes.json")
    p.add_argument("video", type=Path)
    p.add_argument("--cortes", type=Path, required=True)
    p.add_argument("--formato", default="9:16", choices=["original", "9:16", "4:5", "1:1", "16:9"])
    p.add_argument("--enquadrar", default="rosto", choices=["rosto", "centro", "desfocado"])
    p.add_argument("--zoom", default="nao", choices=["nao", "leve", "normal", "forte"])
    p.add_argument("--legenda", default=None, metavar="ESTILO")
    p.add_argument("--ajuste", action="append", metavar="CHAVE=VALOR")
    p.add_argument("--takes", type=Path)

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
            montar(a.video, takes=a.takes, apertar=a.apertar, saida=a.saida, formato=a.formato,
                   enquadrar=a.enquadrar, zoom=a.zoom)
        elif a.cmd == "legendar":
            from .legenda.queimar import legendar
            legendar(a.video, estilo=a.estilo, ajustes=_ajustes(a.ajuste), palavras=a.palavras, idioma=a.idioma, saida=a.saida,
                     gancho=a.gancho, gancho_ate=a.gancho_ate, cta=a.cta, cta_em=a.cta_em, barra=a.barra, sons=a.sons)
        elif a.cmd == "previa":
            from .legenda.queimar import previa
            previa(a.video, estilo=a.estilo, ajustes=_ajustes(a.ajuste), palavras=a.palavras, idioma=a.idioma, em=a.em)
        elif a.cmd == "corrigir":
            from .corrigir import corrigir
            corrigir(a.video, a.correcoes)
        elif a.cmd == "texto":
            from .cortes import texto
            texto(a.video)
        elif a.cmd == "cortar":
            from .cortes import cortar
            cortar(a.video, a.cortes, formato=a.formato, enquadrar=a.enquadrar, zoom=a.zoom, legenda=a.legenda,
                   ajustes=_ajustes(a.ajuste), takes=a.takes)
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
