"""Confere se este computador está pronto para editar e diz o que fazer quando não está.

Cada item sai com ✅ ou ❌ e, quando falha, o conserto em português simples. O relatório também vai
para ~/.corta/diagnostico.json (para mandar para o suporte).
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .base import PASTA_USUARIO, RAIZ_PLUGIN, CortaErro, achar_bin, log, salvar_json

REINSTALAR = "rode o instalador de novo: /corta:instalar"


def _versao_ffmpeg(bin_: str) -> tuple[str, int | None]:
    out = subprocess.run([bin_, "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    primeira = out.splitlines()[0] if out else ""
    m = re.search(r"version\s+n?(\d+)\.", primeira)
    return primeira, (int(m.group(1)) if m else None)


def _modelo_baixado(nome: str) -> bool:
    raiz = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface")) / "hub"
    return (raiz / f"models--Systran--faster-whisper-{nome}").exists()


def diagnostico() -> bool:
    itens = []

    def item(nome: str, ok: bool, detalhe: str = "", conserto: str = ""):
        itens.append({"item": nome, "ok": ok, "detalhe": detalhe, "conserto": "" if ok else conserto})
        log(f"{'✅' if ok else '❌'} {nome}{': ' + detalhe if detalhe else ''}")
        if not ok and conserto:
            log(f"   → {conserto}")

    log(f"/corta motor {__version__} · plugin em {RAIZ_PLUGIN}")
    item("Sistema", True, f"{platform.system()} {platform.release()} ({platform.machine()})")
    py = sys.version_info
    item("Python", py >= (3, 11) and py < (3, 13), f"{py.major}.{py.minor}.{py.micro}", REINSTALAR)

    try:
        ff = achar_bin("ffmpeg")
        linha, maior = _versao_ffmpeg(ff)
        # versões "git" (N-12345) não dizem o número: testa o recurso em vez da versão
        teste = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "anullsrc", "-t", "0.1", "-/af", os.devnull,
                                "-f", "null", "-"], capture_output=True, text=True)
        suporta = "Unrecognized option" not in (teste.stderr or "")
        item("ffmpeg", suporta and (maior is None or maior >= 7), f"{linha[:60]} ({ff})",
             "o ffmpeg é antigo (precisa da versão 7 ou mais nova): " + REINSTALAR)
    except CortaErro as e:
        item("ffmpeg", False, str(e), REINSTALAR)
    try:
        item("ffprobe", True, achar_bin("ffprobe"))
    except CortaErro as e:
        item("ffprobe", False, str(e), REINSTALAR)

    for nome, caminho in (("Fontes da legenda", RAIZ_PLUGIN / "assets" / "fontes" / "montserrat-900-normal.ttf"),
                          ("Detector de rosto", RAIZ_PLUGIN / "assets" / "modelos" / "face_detection_yunet_2023mar.onnx"),
                          ("Vídeo de amostra", RAIZ_PLUGIN / "assets" / "amostra" / "amostra.mp4"),
                          ("Estilos de legenda", RAIZ_PLUGIN / "catalogo" / "legendas" / "creator-bold.json")):
        item(nome, caminho.exists(), "", "arquivos do plugin faltando: atualize ou reinstale o plugin (claude plugin update corta)")

    try:
        PASTA_USUARIO.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=PASTA_USUARIO, delete=True) as f:
            f.write(b"ok")
        item("Pasta de trabalho", True, str(PASTA_USUARIO))
    except OSError as e:
        item("Pasta de trabalho", False, f"{PASTA_USUARIO}: {e}", "sem permissão de escrita na pasta do usuário")

    livre = shutil.disk_usage(str(Path.home())).free / 2**30
    item("Espaço em disco", livre >= 10, f"{livre:.1f} GB livres",
         "libere pelo menos 10 GB (vídeos e arquivos temporários pesam vários GB)")

    try:
        from .perfil import carregar, mostrar
        p = carregar()
        mostrar(p)
        modelo = os.environ.get("CORTA_MODELO") or p["whisper"]["modelo"]
        item("Perfil do computador", True, f"{p['encoder']}, transcrição {modelo}")
        item(f"Modelo de transcrição ({modelo})", _modelo_baixado(modelo),
             "baixado" if _modelo_baixado(modelo) else "ainda não baixado",
             "ele baixa sozinho na 1ª edição (1–3 GB); para baixar agora: corta amostra")
    except Exception as e:  # noqa: BLE001 — o diagnóstico nunca pode quebrar
        item("Perfil do computador", False, str(e), REINSTALAR)

    # só procura (sem carregar): OpenCV e faster-whisper juntos no mesmo processo dão conflito no Mac
    import importlib.util
    faltam = [m for m in ("cv2", "faster_whisper", "PIL", "scipy", "soundfile") if importlib.util.find_spec(m) is None]
    item("Bibliotecas", not faltam, "faltando: " + ", ".join(faltam) if faltam else "faster-whisper, OpenCV, Pillow", REINSTALAR)

    if platform.system() == "Windows" and "onedrive" in str(Path.cwd()).lower():
        item("Pasta no OneDrive", False, str(Path.cwd()),
             "vídeos no OneDrive podem estar 'só na nuvem': clique com o botão direito > Sempre manter neste dispositivo")

    ok = all(i["ok"] for i in itens if not i["item"].startswith("Modelo de transcrição"))
    salvar_json(PASTA_USUARIO / "diagnostico.json", {"versao": __version__, "ok": ok, "itens": itens})
    log("\n" + ("✅ Tudo pronto para editar." if ok else "❌ Tem item para consertar (veja as setas →)."))
    return ok
