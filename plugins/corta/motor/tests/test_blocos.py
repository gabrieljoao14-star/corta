from corta.legenda.blocos import limpar_palavra, linha_do_tempo, montar_blocos, unir_hifens
from corta.legenda.estilos import carregar_estilo, nomes_estilos


def ws(texto, passo=0.3, pausas=()):
    out, t = [], 0.0
    for i, p in enumerate(texto.split()):
        if i in pausas:
            t += 0.8
        out.append({"word": p, "start": round(t, 2), "end": round(t + passo - 0.05, 2)})
        t += passo
    return out


def textos(blocos):
    return [" ".join(limpar_palavra(w["word"]) for w in b) for b in blocos]


def test_ate_n_palavras():
    assert all(len(b) <= 3 for b in montar_blocos(ws("um dois três quatro cinco seis sete"), 3))


def test_quebra_na_pausa():
    assert textos(montar_blocos(ws("isso aqui muda tudo", pausas=(2,)), 3)) == ["isso aqui", "muda tudo"]


def test_nao_termina_em_preposicao():
    b = textos(montar_blocos(ws("eu gosto de editar vídeos rápidos"), 3))
    assert not any(t.split()[-1] in ("de", "a", "o") for t in b[:-1])


def test_pontuacao_nas_pontas_e_pergunta():
    assert limpar_palavra("tempo.") == "tempo"
    assert limpar_palavra("bem?") == "bem?"
    assert limpar_palavra("R$ 9.000,") == "R$ 9.000"


def test_hifen_unido():
    assert [w["word"] for w in unir_hifens([{"word": "e", "start": 0, "end": .1}, {"word": "-mail", "start": .1, "end": .3}])] == ["e-mail"]


def test_linha_do_tempo_sem_buraco_curto():
    tl = linha_do_tempo(montar_blocos(ws("um dois três quatro cinco seis"), 3), 10)
    assert tl[0]["fim"] == tl[1]["inicio"]
    for b in tl:
        assert all(a <= z for a, z in b["ativos"])


def test_todos_os_estilos_carregam_e_ajustes():
    for n in nomes_estilos():
        carregar_estilo(n)
    e = carregar_estilo("creator-bold", {"cor": "ffffff", "fonte": "Poppins", "animacao": "bounce", "palavras": "9"})
    assert e["cor"] == "#FFFFFF" and e["fonte"] == "poppins-900-normal" and e["animacao"] == "pulo" and e["palavras"] == 8
