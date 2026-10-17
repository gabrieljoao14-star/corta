"""Teste da instalação: edita o vídeo de amostra do começo ao fim e confere.

A amostra tem 21 s, barulho de fundo, pausas e um recomeço ("Hoje eu vou te mostrar… hoje eu vou te
mostrar como editar"). Passa se: acha os 6 trechos de fala, entende o texto, tira o recomeço, monta,
legenda, monta em 4:5 com zoom e a conferência dá OK. Roda numa pasta temporária e apaga tudo no fim se der certo.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from .base import PASTA_USUARIO, RAIZ_PLUGIN, CortaErro, ler_json, log, salvar_json

AMOSTRA = RAIZ_PLUGIN / "assets" / "amostra" / "amostra.mp4"
PALAVRAS_CHAVE = ["mostrar", "editar", "silêncios", "legenda", "rápido"]


def amostra() -> bool:
    from .legenda.queimar import legendar
    from .montar import montar
    from .preparar import preparar
    from .transcrever import transcrever
    from .trechos import listar
    from .verificar import verificar

    if not AMOSTRA.exists():
        raise CortaErro(f"Vídeo de amostra não encontrado em {AMOSTRA}. Reinstale o plugin.")
    PASTA_USUARIO.mkdir(parents=True, exist_ok=True)
    pasta = Path(tempfile.mkdtemp(prefix="teste-", dir=PASTA_USUARIO))
    video = pasta / "amostra.mp4"
    shutil.copy2(AMOSTRA, video)
    t0 = time.time()
    falhas = []
    try:
        log("1/7 voz e silêncio")
        d = preparar(video, voz="leve", ritmo="rapido")
        if not 5 <= len(d["trechos"]) <= 7:
            falhas.append(f"esperava 6 trechos de fala, achei {len(d['trechos'])}")
        log("2/7 transcrição")
        ws = transcrever(video)
        texto = " ".join(w["word"].lower() for w in ws)
        faltam = [p for p in PALAVRAS_CHAVE if p not in texto]
        if faltam:
            falhas.append(f"a transcrição não entendeu: {', '.join(faltam)}")
        log("3/7 trechos")
        itens = listar(video, isolado="auto")
        recomeco = [it["i"] for it in itens if "mostrar" in it["texto"].lower() and "editar" not in it["texto"].lower()]
        manter = [it["i"] for it in itens if it["i"] not in recomeco]
        job = video.parent / "_corta" / "amostra"
        salvar_json(job / "takes.json", {"manter": manter, "notas": [["", "tirado", f"recomeço T{r:03d}"] for r in recomeco]})
        if not recomeco:
            falhas.append("não achei o recomeço 'Hoje eu vou te mostrar…'")
        log("4/7 montagem")
        editado = montar(video, takes=job / "takes.json")
        log("5/7 legenda, gancho, CTA, barra e sons")
        legendado = legendar(editado, estilo="creator-bold", gancho="Edite sem perder tempo | Veja como",
                             cta="Siga para mais", barra=True, sons="poucos")
        log("6/7 formato 4:5 com zoom (sem rosto na amostra: enquadra no centro)")
        zoom = montar(video, takes=job / "takes.json", formato="4:5", enquadrar="rosto", zoom="normal",
                      saida=video.with_name("amostra (zoom 4x5).mp4"))
        log("7/7 conferência")
        if not verificar(editado):
            falhas.append("a conferência do vídeo montado não passou")
        if not verificar(zoom):
            falhas.append("a conferência do vídeo com zoom não passou")
        if not verificar(legendado):
            falhas.append("a conferência do vídeo legendado não passou")
        texto_final = " ".join(w["word"].lower() for w in ler_json(job / "palavras_saida.json"))
        if texto_final.count("mostrar") != 1:
            falhas.append("o recomeço continuou no vídeo final")
    except CortaErro as e:
        falhas.append(str(e))
    minutos = (time.time() - t0) / 60
    if falhas:
        log(f"\n❌ TESTE FALHOU ({minutos:.1f} min). Arquivos mantidos para diagnóstico em: {pasta}")
        for f in falhas:
            log(f"   - {f}")
        return False
    shutil.rmtree(pasta, ignore_errors=True)
    log(f"\n✅ TUDO CERTO ({minutos:.1f} min). O /corta está pronto para editar neste computador.")
    return True
