# Comandos do motor e tempos

`M` = `"<PLUGIN>/bin/corta"`. `M <comando> --help` mostra todas as opções.

| Comando | Faz | Tempo aproximado (Mac M2, sem placa de vídeo) |
|---|---|---|
| `M preparar V [--voz leve|forte|nao] [--ritmo rapido|natural]` | voz limpa + onde tem fala | ~10 % da duração (forte: ~30 %) |
| `M transcrever V` | transcrição literal por palavra | ~2× a duração da **fala** |
| `M trechos V [--isolado auto|todos|nenhum]` | lista de trechos para os takes | segundos; ~20 s por trecho suspeito |
| `M montar V [--takes T] [--formato] [--enquadrar] [--zoom] [--regioes R]` | monta o vídeo | ~25 % da duração original |
| `M corrigir SAIDA "errado=certo" …` | corrige palavra da transcrição | instantâneo |
| `M texto V` | transcrição em frases com tempo | instantâneo |
| `M regioes V [--de S --ate S]` | acha tela e câmera (aula/tutorial) | ~30 s |
| `M cortar V --cortes C …` | gera os cortes | ~1 min por corte |
| `M previa SAIDA --estilo E [--ajuste …] [--em S]` | 3 quadros com a legenda | segundos |
| `M legendar SAIDA --estilo E [--ajuste …] [--gancho] [--cta] [--cta-em] [--barra] [--sons]` | legenda e acabamento | ~50 % da duração |
| `M verificar SAIDA` | conferência independente | 1–2 min |
| `M estilos` | lista os estilos de legenda | — |
| `M perfil` | o que este computador usa (modelo, gravação) | — |
| `M diagnostico` | confere a instalação e diz o que consertar | segundos |

Windows sem placa NVIDIA: transcrição ~2–4× mais lenta que a tabela. Com NVIDIA: bem mais rápida.

## Ajustes de legenda (`--ajuste chave=valor`)
`fonte` (Montserrat, Poppins, Anton, Bebas Neue, Luckiest Guy, DM Sans, Playfair Display, Inter) ·
`cor`, `destaque`, `cor_contorno`, `cor_brilho`, `fundo_bloco` (#RRGGBB) ·
`tipo_destaque` (cor, caixa, escala, sublinhado, nenhum) · `contorno` (0–20) · `sombra` · `brilho` ·
`palavras` (1–8) · `tamanho` (0,4–2,5) · `posicao` (baixo, centro, topo) ·
`animacao` (pop, pulo, aparecer, subir, nenhuma) · `letras` (maiusculas, normal, minusculas) ·
`giro_destaque` · `escala_destaque`.

## Onde ficam os dados
`<pasta do vídeo>/_corta/<nome>/`: `voz.wav`, `trechos.json`, `palavras.json`, `takes.json`,
`mapa_*.json`, `palavras_*.json`, `rosto.json`, `regioes.json`, prévias e relatórios de conferência.
