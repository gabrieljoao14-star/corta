import numpy as np
import pytest

from corta.base import CortaErro
from corta.enquadrar import filtro, tela_camera
from corta.regioes import _aparar

AULA = {"tela": [126, 92, 708, 536], "camera": [962, 270, 318, 180], "rosto": [0.909, 0.484], "video": [1280, 720]}


def test_layout_soma_1920_e_legenda_na_faixa():
    cadeia, geo = tela_camera(AULA)
    assert geo["ht"] + geo["faixa"] + geo["hc"] == 1920
    assert geo["ht"] / 1920 < geo["y_legenda"] < (geo["ht"] + geo["faixa"]) / 1920
    assert "vstack" in cadeia and "pad=1080" in cadeia


def test_camera_pequena_nao_estica_demais():
    _, geo = tela_camera(AULA)
    assert geo["hc"] <= 180 * 3.6 + 2


def test_camera_recortada_dentro_do_quadro_e_no_rosto():
    _, geo = tela_camera(AULA)
    x, y, w, h = geo["camera"]
    cx, cy, cw, ch = AULA["camera"]
    assert cx <= x and x + w <= cx + cw and cy <= y and y + h <= cy + ch
    assert x <= 0.909 * 1280 <= x + w


def test_tela_alta_mostra_o_topo():
    _, geo = tela_camera({**AULA, "tela": [0, 0, 600, 1200]})
    assert geo["ht"] <= 1000 and geo["tela"][1] == 0


def test_tela_camera_exige_regioes_e_vertical():
    with pytest.raises(CortaErro):
        filtro(1280, 720, "9:16", "tela-camera", "nao", [(0, 5)], [(0.5, 0.5)])
    with pytest.raises(CortaErro):
        filtro(1280, 720, "16:9", "tela-camera", "nao", [(0, 5)], [(0.5, 0.5)], AULA)


def test_aparar_tira_barra_lateral_sem_texto():
    img = np.full((400, 800), 230, np.uint8)
    for y in range(20, 380, 12):              # "linhas de texto" entre x=200 e x=640
        img[y:y + 3, 200:640] = 20
    x, _, w, _ = _aparar(img, [0, 0, 800, 400])
    assert 150 <= x <= 200 and 640 <= x + w <= 700
