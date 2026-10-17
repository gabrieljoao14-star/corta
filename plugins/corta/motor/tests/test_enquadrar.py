import pytest

from corta.base import CortaErro
from corta.cortes import _tempo
from corta.enquadrar import PLANO_MIN, filtro, planos


def ws(n, passo=0.4, fim_frase=()):
    return [{"word": f"p{i}{'.' if i in fim_frase else ''}", "start": i * passo, "end": i * passo + 0.3} for i in range(n)]


def test_planos_respeitam_tamanho_minimo_e_cobrem_tudo():
    ps = planos(ws(40, fim_frase=(2, 4, 10, 20)), [[0, 5], [5, 16]], 16.0)
    assert ps[0][0] == 0 and ps[-1][1] == 16.0
    assert all(b > a for a, b in ps)
    inicios = [a for a, _ in ps]
    assert all(b - a >= PLANO_MIN - 1e-6 for a, b in zip(inicios, inicios[1:]))
    assert 5.0 in inicios                       # todo corte da montagem vira troca de plano


def test_plano_longo_ganha_corte_no_meio():
    ps = planos(ws(30), [[0, 12]], 12.0)        # nenhuma frase termina: 12 s seguidos
    assert len(ps) >= 2


def test_filtro_vertical_de_horizontal_recorta_no_rosto():
    cadeia, ow, oh, geo = filtro(1920, 1080, "9:16", "rosto", "normal", [(0, 3), (3, 6)], [(0.7, 0.4), (0.3, 0.4)])
    assert (ow, oh) == (1080, 1920)
    assert geo["cw"] == 608 and geo["ch"] == 1080
    assert "crop=608:1080" in cadeia and "scale=1080:1920" in cadeia
    assert "iw" not in cadeia.split("crop=")[1]   # o crop não pode depender do iw (fica preso no 1º quadro)


def test_filtro_sem_mudanca_nao_mexe():
    cadeia, ow, oh, _ = filtro(1080, 1920, None, "rosto", "nao", [(0, 5)], [(0.5, 0.4)])
    assert (ow, oh) == (1080, 1920) and "crop" not in cadeia and "eval=frame" not in cadeia


def test_desfocado_e_valores_invalidos():
    cadeia, *_ = filtro(1920, 1080, "9:16", "desfocado", "nao", [(0, 5)], [(0.5, 0.5)])
    assert "boxblur" in cadeia
    with pytest.raises(CortaErro):
        filtro(1920, 1080, "3:2", "rosto", "nao", [(0, 5)], [(0.5, 0.5)])


def test_tempos_dos_cortes():
    assert _tempo("12:03.4") == pytest.approx(723.4)
    assert _tempo("1:02:03") == pytest.approx(3723)
    assert _tempo(95) == 95.0 and _tempo("95,5") == 95.5
    with pytest.raises(CortaErro):
        _tempo("amanhã")
