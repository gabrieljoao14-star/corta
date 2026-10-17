"""Perfil do computador: decide modelo de transcrição, aceleração do vídeo e limpeza de voz.

Medido uma vez na instalação e salvo em ~/.corta/perfil.json. Tudo que depende da máquina
sai daqui, para que a receita seja a mesma no Mac e no Windows.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess

import psutil

from .base import PASTA_USUARIO, ffmpeg, ler_json, log, salvar_json

ARQ = PASTA_USUARIO / "perfil.json"


def _nvidia() -> dict | None:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15).stdout.strip().splitlines()
        nome, mem = [x.strip() for x in out[0].split(",")]
        return {"nome": nome, "memoria_mb": int(float(mem))}
    except Exception:
        return None


def _cuda_para_whisper() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _encoder_funciona(enc: str, extra: list) -> bool:
    cmd = [ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=1",
           "-c:v", enc, *extra, "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


ENCODERS = {
    # nome: (argumentos de qualidade alta, sistemas em que vale tentar)
    "h264_videotoolbox": (["-b:v", "16M", "-allow_sw", "1"], {"Darwin"}),
    "h264_nvenc": (["-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"], {"Windows", "Linux"}),
    "h264_qsv": (["-global_quality", "20"], {"Windows", "Linux"}),
    "h264_amf": (["-quality", "quality", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20"], {"Windows"}),
    "libx264": (["-crf", "18", "-preset", "veryfast"], {"Darwin", "Windows", "Linux"}),
}


def detectar() -> dict:
    so = platform.system()
    ram_gb = psutil.virtual_memory().total / 2**30
    disco_gb = shutil.disk_usage(str(PASTA_USUARIO.parent)).free / 2**30
    gpu = _nvidia()
    cuda = _cuda_para_whisper()

    encoder = "libx264"
    for nome, (args, sistemas) in ENCODERS.items():
        if so in sistemas and nome != "libx264" and _encoder_funciona(nome, args):
            encoder = nome
            break

    if cuda:
        whisper = {"modelo": "large-v2", "device": "cuda", "compute": "float16"}
    elif ram_gb >= 12:
        whisper = {"modelo": "large-v2", "device": "cpu", "compute": "int8"}
    else:
        whisper = {"modelo": "medium", "device": "cpu", "compute": "int8"}

    try:
        import demucs  # noqa: F401
        tem_forte = True
    except Exception:
        tem_forte = False
    apple = so == "Darwin" and platform.machine() == "arm64"
    # sem placa (NVIDIA ou chip Apple) a limpeza forte leva ~tempo real ou mais: o padrão vira a leve
    voz_padrao = "forte" if tem_forte and (cuda or apple) else "leve"

    return {
        "sistema": so, "versao_sistema": platform.release(), "maquina": platform.machine(),
        "cpus": os.cpu_count(), "ram_gb": round(ram_gb, 1), "disco_livre_gb": round(disco_gb, 1),
        "gpu_nvidia": gpu, "whisper": whisper, "encoder": encoder,
        "encoder_args": ENCODERS[encoder][0], "limpeza_forte_instalada": tem_forte, "voz_padrao": voz_padrao,
    }


def carregar(recalcular: bool = False) -> dict:
    if ARQ.exists() and not recalcular:
        return ler_json(ARQ)
    p = detectar()
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    salvar_json(ARQ, p)
    return p


def args_video(perfil: dict) -> list:
    return ["-c:v", perfil["encoder"], *perfil["encoder_args"], "-pix_fmt", "yuv420p"]


def mostrar(p: dict) -> None:
    gpu = p["gpu_nvidia"]["nome"] if p["gpu_nvidia"] else "nenhuma NVIDIA"
    log(f"Sistema: {p['sistema']} {p['versao_sistema']} ({p['maquina']}) · {p['cpus']} núcleos · {p['ram_gb']} GB de memória")
    log(f"Disco livre: {p['disco_livre_gb']} GB · placa de vídeo: {gpu}")
    log(f"Transcrição: {p['whisper']['modelo']} em {p['whisper']['device']} · gravação de vídeo: {p['encoder']}")
    log(f"Limpeza de voz padrão: {p['voz_padrao']} (forte instalada: {'sim' if p['limpeza_forte_instalada'] else 'não'})")
    if p["disco_livre_gb"] < 10:
        log("⚠️  Menos de 10 GB livres: libere espaço antes de editar vídeos longos.")
