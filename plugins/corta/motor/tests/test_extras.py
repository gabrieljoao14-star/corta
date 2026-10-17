import numpy as np

from corta.legenda.estilos import carregar_estilo
from corta.legenda.extras import Camada, eventos, som, viradas


def caixa(img):
    return img.getchannel("A").getbbox()


def test_viradas_poucos_e_todos():
    planos = [[0, 3, 1.1], [3, 6, 1.0], [6, 9, 1.18], [9, 12, 1.06], [12, 20, 1.24], [20, 25, 1.0]]
    poucos = viradas(planos, "poucos")
    assert 1 <= len(poucos) <= 3 and all(b - a >= 6 for a, b in zip(poucos, poucos[1:]))
    assert len(viradas(planos, "todos")) == 5
    assert viradas(planos, "nao") == [] and viradas([], "poucos") == []


def test_sons_tem_volume_baixo_e_sem_estouro():
    for n in ("whoosh", "pop", "impacto"):
        s = som(n)
        assert 0.05 < np.abs(s).max() < 0.25 and len(s) < 48000


def test_gancho_fica_fora_da_zona_proibida_e_cta_cabe_na_tela():
    c = Camada(carregar_estilo("creator-bold"), 1080, 1920)
    g = caixa(c.gancho("Seu cliente pediu justiça gratuita? | A resposta mudou"))
    assert g[1] >= int(1920 * 0.16) - 30           # começa logo abaixo dos 16 % de cima
    cta = caixa(c.cta("Aula gratuita e ao vivo toda quarta · Toque em Saiba mais", 1.0))
    assert cta[0] >= 0 and cta[2] <= 1080 and cta[3] <= int(1920 * 0.76)   # fora dos 24 % de baixo


def test_eventos_cobrem_gancho_e_cta(tmp_path):
    c = Camada(carregar_estilo("karaoke"), 1080, 1920)
    ev = eventos(c, tmp_path, 20.0, "Pare de perder tempo", 3.0, "Siga para mais", 16.0)
    assert ev[0][0] == 0.0 and any(a >= 16.0 for a, _, _ in ev)
    assert all(b > a for a, b, _ in ev)
    assert max(b for a, b, _ in ev if a < 10) <= 3.0 + 1e-6
