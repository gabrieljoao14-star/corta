"""Confere uma saída do motor de forma independente (nota 04: nunca comparar a saída com os
próprios dados que a geraram). Mede no ARQUIVO FINAL:

[1] imagem e som com a mesma duração;
[2] nenhuma fala sumiu nos trechos tirados como silêncio (os takes tirados de propósito não contam);
[3] o som de cada pedaço é a voz certa do original (semelhança no ponto mapeado);
[4] a imagem de cada pedaço é o quadro certo do original (6 pontos, tolerância 2 quadros);
[5] volume final e maior pausa que sobrou;
[6] se tem legenda: re-transcreve 3 janelas do arquivo final e mede o atraso da legenda.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from .base import (CortaErro, ffmpeg, ffprobe, info_video, ler_json, log, rodar, saida_registrada, salvar_json)


PICO_FUNDO_DB = -30   # mesma regra da preparação: abaixo disso é voz de fundo, sai de propósito


def _wav16(src: Path, dst: Path) -> np.ndarray:
    rodar([ffmpeg(), "-y", "-v", "error", "-i", src, "-map", "0:a:0", "-ac", 1, "-ar", 16000, dst], descricao="áudio")
    x, _ = sf.read(dst, dtype="float32")
    dst.unlink(missing_ok=True)
    return x


def _cinza(arq: Path, t: float, retrato: bool) -> np.ndarray:
    tam = "90:160" if retrato else "160:90"
    out = subprocess.run([ffmpeg(), "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", str(arq), "-frames:v", "1",
                          "-vf", f"scale={tam},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(out, np.uint8).astype(np.int16)


def _db(x, jan):
    n = len(x) // jan
    return 20 * np.log10(np.sqrt((x[: n * jan].reshape(n, jan) ** 2).mean(1)) + 1e-9) if n else np.array([-120.0])


def _norm(p):
    return re.sub(r"[^\wà-ú]", "", p.lower())


def verificar(saida: Path) -> bool:
    saida = saida.resolve()
    if not saida.exists():
        raise CortaErro(f"Não achei {saida}")
    reg = saida_registrada(saida)
    info = info_video(saida)
    relatorio, ok = {"arquivo": str(saida)}, True
    log(f"===== conferindo {saida.name}")

    # [1]
    pr = rodar([ffprobe(), "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", saida]).stdout
    durs = {l.split(",")[0]: float(l.split(",")[1]) for l in pr.strip().splitlines() if "," in l and l.split(",")[1] not in ("", "N/A")}
    dv, da = durs.get("video", info["duracao"]), durs.get("audio", 0.0)
    dif = abs(dv - da) * 1000
    log(f"[1] {info['largura']}x{info['altura']} · imagem {dv:.3f} s · som {da:.3f} s · diferença {dif:.0f} ms")
    ok &= dif < 60
    relatorio["duracao"] = {"video": dv, "audio": da, "ok": dif < 60}

    if not reg or not reg.get("mapa"):
        log("    (sem dados da montagem: só a conferência básica)")
        log("RESULTADO: " + ("OK" if ok else "ATENÇÃO"))
        return ok

    job = Path(reg["mapa"]).parent      # pasta do vídeo ORIGINAL (a legenda é registrada na pasta do editado)
    mapa_d = ler_json(reg["mapa"])
    mapa = mapa_d["mapa"]
    dados = ler_json(job / "trechos.json")
    original = Path(dados["video"])
    trechos = dados["trechos"]
    voz = _wav16(job / "voz.wav", job / "_v16.wav")
    fim = _wav16(saida, job / "_f16.wav")

    # [2] fala em trecho tirado como silêncio (não em take tirado de propósito)
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    tirados, prev = [], 0.0
    for s, e in trechos:
        if s - prev > 0.15:
            tirados.append((prev, s))
        prev = e
    if dados["info"]["duracao"] - prev > 0.15:
        tirados.append((prev, dados["info"]["duracao"]))
    mantidos = [m["original"] for m in mapa]
    suspeitos = []
    for a, b in tirados:
        # ignora a borda que a montagem recuperou
        if any(ma <= a + 0.05 and b - 0.05 <= mb for ma, mb in mantidos):
            continue
        seg = voz[int(a * 16000): int(b * 16000)]
        if len(seg) < 2400 or (_db(seg, 320) > -40).sum() * 0.02 < 0.08:
            continue
        ts = get_speech_timestamps(seg, VadOptions(threshold=0.3, min_speech_duration_ms=150, min_silence_duration_ms=100, speech_pad_ms=0))
        # só o miolo: a 0,2 s das bordas ainda é a fala do trecho vizinho
        miolo = [(max(t["start"], 3200), min(t["end"], len(seg) - 3200)) for t in ts]
        miolo = [(x, y) for x, y in miolo if y - x >= 2400]
        if miolo:
            suspeitos.append((a, b, max(float(_db(seg[x:y], 320).max()) for x, y in miolo), miolo))
    confirmados = []
    if suspeitos:
        from .transcrever import modelo
        m = modelo()
        for a, b, pico, miolo in suspeitos[:15]:
            pad = np.zeros(8000, np.float32)
            base = voz[int(a * 16000): int(b * 16000)]
            seg = np.concatenate([pad] + [np.concatenate([base[x:y], pad]) for x, y in miolo])
            txt = " ".join(z.text for z in m.transcribe(seg, language="pt", vad_filter=False, condition_on_previous_text=False)[0]
                           if z.no_speech_prob < 0.5).strip()
            if txt:
                confirmados.append({"de": round(a, 2), "ate": round(b, 2), "texto": txt, "pico_db": round(pico, 1),
                                    "fundo": pico < PICO_FUNDO_DB})
    tirado_s = sum(b - a for a, b in tirados)

    # [2b] palavra de um take mantido que a montagem (aperto das pausas) deixou de fora
    perdidas = []
    if (job / "palavras.json").exists() and (job / "palavras_saida.json").exists():
        ws = ler_json(job / "palavras.json")
        n_saida = len(ler_json(job / "palavras_saida.json"))
        plano = ler_json(mapa_d["takes"])["manter"] if mapa_d.get("takes") else list(range(len(trechos)))
        faixas = []
        for it in plano:
            i, so, eo = (it, None, None) if isinstance(it, int) else it
            faixas.append((so if so is not None else trechos[i][0], eo if eo is not None else trechos[i][1]))
        dentro = [w for w in ws if any(fa <= (w["start"] + w["end"]) / 2 <= fb for fa, fb in faixas)]
        for w in dentro:
            meio = (w["start"] + w["end"]) / 2
            if not any(ma <= meio < mb for ma, mb in mantidos):
                perdidas.append(w)
        relatorio["palavras_cortadas"] = perdidas
    fortes = [c for c in confirmados if not c["fundo"]]
    log(f"[2] {len(tirados)} pausas tiradas ({tirado_s:.1f} s) · com som de voz: {len(suspeitos)} · "
        f"voz de fundo tirada de propósito: {len(confirmados) - len(fortes)} · fala de quem apresenta tirada: {len(fortes)}")
    for c in confirmados:
        tipo = "voz baixa de fundo (quem filma?)" if c["fundo"] else "⚠ conferir: fala alta fora dos trechos (quem filma ou fala perdida?)"
        log(f"    {c['de']:.1f}–{c['ate']:.1f} s do original ({c['pico_db']} dB, {tipo}): \"{c['texto']}\"")
    if perdidas:
        log(f"    ⚠ {len(perdidas)} palavra(s) na borda de um take ficaram de fora: "
            + ", ".join(f"'{w['word']}' ({w['start']:.1f} s)" for w in perdidas[:8]))
    relatorio["fala_tirada"] = confirmados
    avisos = len(fortes)
    ok &= not perdidas

    # [3] som certo em cada pedaço
    nccs = []
    for m_ in mapa:
        (a, b), (sa, sb) = m_["original"], m_["saida"]
        if b - a > 1.2:
            meio_o, meio_s = (a + b) / 2, (sa + sb) / 2
            f = fim[int((meio_s - 0.25) * 16000):][:8000]
            v = voz[int((meio_o - 0.25) * 16000):][: len(f)]
            if len(f) == len(v) and np.sqrt((f ** 2).mean()) > 0.01:
                nccs.append(float(np.dot(v, f) / (np.linalg.norm(v) * np.linalg.norm(f) + 1e-12)))
    if nccs:
        log(f"[3] som × original em {len(nccs)} pedaços: semelhança mínima {min(nccs):.3f} · mediana {np.median(nccs):.3f}")
        ok &= min(nccs) > 0.8
        relatorio["som"] = {"min": min(nccs), "mediana": float(np.median(nccs))}
    else:
        log("[3] pedaços curtos demais para medir o som")

    # [4] imagem certa
    F = mapa_d["fps"]
    retrato = info["altura"] > info["largura"]
    pior = 0
    pontos = [m_ for m_ in mapa if m_["saida"][1] - m_["saida"][0] > 1.0]
    pontos = [pontos[i] for i in np.linspace(0, len(pontos) - 1, min(6, len(pontos))).astype(int)] if pontos else []
    for m_ in pontos:
        (a, _), (sa, sb) = m_["original"], m_["saida"]
        t = (sa + sb) / 2
        ref = _cinza(original, a + (t - sa), retrato)
        # média (não mediana: em quadro parado a mediana dá 0 em tudo) e, no empate, o menor desvio
        melhor = min(((np.abs(_cinza(saida, t + d / F, retrato) - ref).mean(), abs(d), d) for d in range(-3, 4)))[1:]
        pior = max(pior, abs(melhor[1]))
    if pontos:
        log(f"[4] imagem × original ({len(pontos)} pontos): pior desvio {pior} quadro(s)")
        ok &= pior <= 2
        relatorio["imagem_desvio_quadros"] = int(pior)

    # [5] volume e pausas
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(
        [ffmpeg(), "-hide_banner", "-i", str(saida), "-map", "0:a:0", "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace").stderr)
    quieto = _db(fim, 160) < -45
    maior, run_ = 0, 0
    for q in quieto:
        run_ = run_ + 1 if q else 0
        maior = max(maior, run_)
    log(f"[5] volume {lufs[-1] if lufs else '?'} LUFS · maior pausa que sobrou {maior * 0.01:.2f} s")
    relatorio["volume_lufs"] = float(lufs[-1]) if lufs else None
    relatorio["maior_pausa"] = maior * 0.01

    # [6] legenda
    if reg.get("etapa") == "legendar" and reg.get("palavras") and Path(reg["palavras"]).exists():
        from .transcrever import modelo
        ref = ler_json(reg["palavras"])
        m = modelo()
        desvios = []
        for c in np.linspace(0.15, 0.85, 3) * dv:
            a = max(0.0, c - 5)
            seg = fim[int(a * 16000): int((a + 10) * 16000)]
            ws = [w for z in m.transcribe(seg, language="pt", word_timestamps=True, vad_filter=False,
                                          condition_on_previous_text=False)[0] for w in (z.words or [])]
            for w in ws:
                t, n = a + w.start, _norm(w.word)
                cand = [r_ for r_ in ref if _norm(r_["word"]) == n and abs(r_["start"] - t) < 1.0]
                if n and cand:
                    desvios.append(min((r_["start"] - t for r_ in cand), key=abs))
        if desvios:
            med = float(np.median(desvios))
            log(f"[6] legenda × fala (re-transcrição de 3 janelas, {len(desvios)} palavras): atraso mediano {med * 1000:+.0f} ms")
            ok &= abs(med) < 0.15
            relatorio["legenda_atraso_ms"] = round(med * 1000)
    for tmp in (job / "_v16.wav", job / "_f16.wav"):
        tmp.unlink(missing_ok=True)
    relatorio["ok"] = bool(ok)
    relatorio["avisos"] = avisos
    salvar_json(job / f"verificacao_{saida.stem}.json", relatorio)
    if ok and avisos:
        log(f"RESULTADO: OK ✅ com {avisos} aviso(s) para conferir (ouça o trecho do original citado em [2])")
    else:
        log("RESULTADO: " + ("OK ✅" if ok else "ATENÇÃO ⚠️"))
    return bool(ok)
