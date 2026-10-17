"""Peças comuns: achar ffmpeg, rodar comandos, ler o vídeo, pasta de trabalho, JSON.

Regras que valem para o motor inteiro (vieram das lições das notas 01–04):
- nunca sobrescrever o original nem uma saída anterior (`saida_livre`);
- caminhos sempre como lista de argumentos, nunca string de shell (acentos e espaços no Windows);
- texto em UTF-8 de ponta a ponta.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ_PLUGIN = Path(os.environ.get("CORTA_RAIZ") or Path(__file__).resolve().parents[3])
PASTA_USUARIO = Path(os.environ.get("CORTA_HOME") or (Path.home() / ".corta"))
EXE = ".exe" if os.name == "nt" else ""


class CortaErro(Exception):
    """Erro com mensagem para a pessoa (em português simples, com o que fazer)."""


def log(msg: str) -> None:
    print(msg, flush=True)


def achar_bin(nome: str) -> str:
    env = os.environ.get(f"CORTA_{nome.upper()}")
    if env and Path(env).exists():
        return env
    local = PASTA_USUARIO / "bin" / f"{nome}{EXE}"
    if local.exists():
        return str(local)
    achado = shutil.which(nome)
    if achado:
        return achado
    raise CortaErro(f"Não achei o {nome}. Rode a instalação de novo: /corta:instalar")


def ffmpeg() -> str:
    return achar_bin("ffmpeg")


def ffprobe() -> str:
    return achar_bin("ffprobe")


def rodar(cmd: list, *, descricao: str = "") -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        nome = descricao or Path(cmd[0]).name
        raise CortaErro(f"Falhou: {nome}\n{r.stderr[-2000:]}")
    return r


def info_video(caminho: Path) -> dict:
    r = rodar([ffprobe(), "-v", "error", "-show_streams", "-show_format", "-of", "json", caminho], descricao="ffprobe")
    js = json.loads(r.stdout)
    v = next((s for s in js["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in js["streams"] if s.get("codec_type") == "audio"), None)
    if v is None:
        raise CortaErro(f"{caminho.name} não tem imagem de vídeo.")
    w, h = int(v["width"]), int(v["height"])
    # vídeo do celular gravado "deitado": o ffmpeg gira sozinho ao decodificar, então troca largura/altura
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    dur = float(js["format"].get("duration") or v.get("duration") or 0)
    return {"largura": w, "altura": h, "fps": fps, "duracao": dur, "tem_audio": a is not None}


def fps_saida(fps: float) -> int:
    """Quadro inteiro e que divide 48 kHz (cada quadro = N amostras exatas): 29,97 → 30, 23,976 → 24."""
    f = int(round(fps)) or 30
    f = min(f, 60)
    return f if 48000 % f == 0 else 30


def nome_seguro(texto: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip() or "video"


def pasta_job(video: Path) -> Path:
    p = video.parent / "_corta" / nome_seguro(video.stem)
    p.mkdir(parents=True, exist_ok=True)
    return p


def saida_livre(desejada: Path) -> Path:
    """Nunca sobrescreve: se o arquivo existe, vira 'nome (2).mp4', 'nome (3).mp4'…"""
    if not desejada.exists():
        return desejada
    i = 2
    while True:
        c = desejada.with_name(f"{desejada.stem} ({i}){desejada.suffix}")
        if not c.exists():
            return c
        i += 1


def ler_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def salvar_json(p: Path, dados) -> None:
    Path(p).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def conferir_arquivo_local(video: Path) -> None:
    """OneDrive/iCloud podem deixar o arquivo 'só na nuvem': existe na pasta mas não tem os dados."""
    if not video.exists():
        raise CortaErro(f"Não achei o arquivo: {video}")
    try:
        with open(video, "rb") as f:
            f.read(1024)
    except OSError as e:
        raise CortaErro(f"Não consegui ler {video.name}. Se ele está no OneDrive ou iCloud, baixe para o computador primeiro. ({e})")
    if video.stat().st_size < 1024:
        raise CortaErro(f"{video.name} parece vazio ou só na nuvem. Baixe o arquivo para o computador e tente de novo.")


class Cronometro:
    def __init__(self, nome: str):
        self.nome, self.t0 = nome, time.time()

    def fim(self) -> float:
        s = time.time() - self.t0
        log(f"   ({self.nome}: {s / 60:.1f} min)" if s >= 60 else f"   ({self.nome}: {s:.0f} s)")
        return s


def configurar_saida_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def registrar_saida(job: Path, item: dict) -> None:
    """Anota a saída no job e num índice global (~/.corta/saidas.json): assim a legenda acha as
    palavras certas mesmo se o vídeo editado for movido para outra pasta... desde que o caminho não mude."""
    reg = job / "saidas.json"
    lista = ler_json(reg) if reg.exists() else []
    lista.append(item)
    salvar_json(reg, lista)
    glob_ = PASTA_USUARIO / "saidas.json"
    PASTA_USUARIO.mkdir(parents=True, exist_ok=True)
    try:
        indice = ler_json(glob_) if glob_.exists() else {}
    except ValueError:
        indice = {}
    indice[item["arquivo"]] = {**item, "job": str(job)}
    salvar_json(glob_, indice)


def saida_registrada(arquivo: Path) -> dict | None:
    glob_ = PASTA_USUARIO / "saidas.json"
    if not glob_.exists():
        return None
    try:
        return ler_json(glob_).get(str(Path(arquivo).resolve()))
    except ValueError:
        return None
