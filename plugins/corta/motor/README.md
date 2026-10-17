# Motor do /corta

Comandos de edição que o Claude roda. Funcionam no Mac e no Windows; o computador é medido uma vez
(`corta perfil`) e as configurações saem dali. Rodar sempre com `uv run --project <esta pasta> corta …`.

Os dados de cada vídeo ficam em `<pasta do vídeo>/_corta/<nome>/`. O original nunca é alterado e
nenhuma saída é sobrescrita (`nome (editado).mp4`, `nome (editado) (2).mp4`…).

## Fluxo de um vídeo falado

| Etapa | Comando | O que sai |
|---|---|---|
| 1. Voz e silêncio | `corta preparar VIDEO --voz leve --ritmo rapido` | `voz.wav`, `trechos.json` |
| 2. Transcrição literal | `corta transcrever VIDEO` | `palavras.json` |
| 3. Lista para decidir os takes | `corta trechos VIDEO` | lista `T000…` com ⚠ nos suspeitos, `trechos_texto.json` |
| 4. Decisão | o Claude escreve `takes.json` e mostra para a pessoa | `takes.json` |
| 5. Montagem | `corta montar VIDEO --takes …/takes.json` | `VIDEO (editado).mp4` |
| 6. Prévia da legenda | `corta previa "VIDEO (editado).mp4" --estilo creator-bold` | `previa_creator-bold.png` |
| 7. Legenda | `corta legendar "VIDEO (editado).mp4" --estilo creator-bold --ajuste destaque=#22D3EE` | `VIDEO (legendado).mp4` |
| 8. Conferência | `corta verificar "VIDEO (legendado).mp4"` | `RESULTADO: OK ✅` (ou com avisos para conferir) |

Só tirar silêncio: pular 2–4 e rodar `corta montar VIDEO` sem `--takes`.
Correção de palavra errada da transcrição (antes da legenda): `corta corrigir "VIDEO (editado).mp4" lerite=holerite`.

### Formato, enquadramento e zoom (na mesma passada da montagem)
`corta montar VIDEO --takes … --formato 9:16 --enquadrar rosto --zoom normal`
- `--formato`: original (padrão), 9:16, 4:5, 1:1, 16:9.
- `--enquadrar`: `rosto` (segue o rosto; detector YuNet, igual no Mac e no Windows), `centro`, `desfocado`
  (vídeo inteiro sobre fundo desfocado).
- `--zoom`: nao, leve, normal, forte. Troca o enquadramento em cada corte da montagem (esconde o pulo),
  no começo de frase e no meio de frase longa; respiração lenta de 1,5 % dentro do plano.

## Cortes de vídeo longo (live, podcast, aula)
| Etapa | Comando |
|---|---|
| 1. Preparar com ritmo natural | `corta preparar LIVE.mp4 --ritmo natural` e `corta transcrever LIVE.mp4` |
| 2. Ler o texto inteiro | `corta texto LIVE.mp4` (frases com tempo) |
| 3. Escolher e aprovar | o Claude escreve `cortes.json` e mostra a tabela para a pessoa aprovar |
| 4. Gerar | `corta cortar LIVE.mp4 --cortes cortes.json --formato 9:16 --zoom leve --legenda creator-bold` |

`cortes.json`: `{"cortes": [{"nome": "Prazo que ninguém conta", "inicio": "12:03.4", "fim": "12:58.0"}]}`.
Bom corte: gancho nos 3 primeiros segundos, se sustenta sozinho, fecha a ideia, 25–90 s.
Os cortes saem em `LIVE - cortes/01 - nome (legendado).mp4`, já sem pausas e no rosto.
Só legendar um vídeo pronto: `corta legendar VIDEO --estilo …` (transcreve sozinho).

### `takes.json`
```json
{"manter": [3, 4, [7, 12.40, null], 9],
 "notas": [["0:21", "tirado", "recomeço: Hoje eu vou…"], ["0:24", "MANTIDO", "último take completo"]]}
```
Número = trecho inteiro. `[trecho, início, fim]` = corta dentro do trecho (tempo do original; `null` mantém a borda).

### Critério dos takes (aprovado nas notas 01)
- Frase recomeçada ou repetida: fica o **último take completo**.
- Sai toda fala de **quem está filmando** e orientação de atuação.
- Sai ênfase solta que não faz sentido sozinha e conversa depois do fim.
- Trecho com ⚠ (lento, palavra esticada, repetição, curto): ler a versão isolada antes de decidir.
- Decisão de conteúdo é da pessoa: mostrar a lista MANTIDO/tirado antes de montar.

## Legenda
`corta estilos` lista os estilos. Ajustes aceitos (`--ajuste chave=valor`, pode repetir):
`fonte` (Montserrat, Poppins, Anton, Bebas Neue, Luckiest Guy, DM Sans, Playfair Display, Inter),
`cor`, `destaque`, `cor_contorno`, `cor_brilho`, `fundo_bloco` (#RRGGBB), `tipo_destaque`
(cor, caixa, escala, sublinhado, nenhum), `contorno` (0–20), `sombra`, `brilho`, `palavras` (1–8),
`tamanho` (0,4–2,5), `posicao` (baixo, centro, topo), `animacao` (pop, pulo, aparecer, subir, nenhuma),
`letras` (maiusculas, normal, minusculas), `giro_destaque`, `escala_destaque`.

A legenda é desenhada em imagem com as fontes do plugin (licença aberta) e colada pelo ffmpeg:
sai igual no Mac e no Windows. `--estilo nenhuma` grava só o acabamento abaixo, sem legenda.

### Acabamento (na mesma gravação da legenda)
`corta legendar VIDEO --estilo creator-bold --gancho "Seu cliente pediu justiça gratuita? | A resposta mudou" --cta "Aula gratuita · Toque em Saiba mais" --cta-em 50.3 --barra --sons poucos`
- `--gancho`: texto no topo, logo abaixo dos 16 % que o Reels cobre; palavras entram uma a uma.
  `pergunta | resposta` = 2 níveis (resposta numa faixa na cor de destaque). Sai sozinho no fim da 1ª
  pergunta ou em 3,5 s (`--gancho-ate` muda). Texto do gancho e do CTA é decisão da pessoa: mostrar antes.
- `--cta`: chamada que sobe acima da legenda, fora dos 24 % de baixo. `--cta-em` = segundo em que entra
  (o começo da fala da chamada, tirado da transcrição); padrão 4 s antes do fim. "A · B" quebra em 2 linhas.
  No anúncio do Meta o link é o botão: use "Toque em Saiba mais", não "link na descrição".
- `--barra`: barra de progresso no topo, na cor de destaque.
- `--sons`: `poucos` = impacto no gancho, pop no CTA e até 3 whooshes nas maiores trocas de zoom;
  `todos` = whoosh em toda troca de plano. Sons gerados por código (sem direitos autorais), baixinhos.

## Teste
`corta amostra` edita `assets/amostra/amostra.mp4` do começo ao fim e confere. É o último passo da
instalação e roda no GitHub em Mac e Windows a cada mudança (`.github/workflows/motor.yml`).
A amostra atual tem voz sintética do Mac (provisória): trocar por uma gravação própria de 15–20 s.
