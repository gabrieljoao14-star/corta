# Formato da receita (versão 1)

A receita vem do app /corta (ou é escrita à mão). Uma linha por campo, `campo: valor`; opções separadas
por `·`. Campos que faltarem usam o padrão. Linha que você não reconhecer: ignore e avise a pessoa.

```
/corta:editar
receita: corta/1 · Reels falado rápido
formato: 9:16
limpeza: silencio=rapido · erros-de-fala=sim · voz=leve
legenda: creator-bold
  ajustes: fonte=Montserrat · destaque=#FFE14D · palavras=3 · posicao=baixo · animacao=pop · letras=maiusculas
movimento: zoom=normal · enquadrar=rosto
acabamento: gancho=sugerir · cta="Toque em Saiba mais" · barra=sim · sons=poucos
aprovacao: conteudo
idioma: pt
videos:
  - /Users/ana/Videos/gravacao 1.mov
```

| Campo | Valores | Padrão | Vira no motor |
|---|---|---|---|
| `receita` | `corta/1` + nome do tipo de edição | — | se a versão for maior que 1, diga para atualizar o plugin (`claude plugin update corta`) |
| `formato` | `9:16`, `4:5`, `1:1`, `16:9`, `original`, `cortes` | `original` | `montar --formato` (cortes: fluxo de cortes, sempre 9:16) |
| `limpeza.silencio` | `rapido`, `natural`, `nao` | `rapido` | `preparar --ritmo` (nao: não monta, só legenda) |
| `limpeza.erros-de-fala` | `sim`, `nao` | `sim` | transcrever + trechos + takes.json |
| `limpeza.voz` | `leve`, `forte`, `nao` | o do perfil | `preparar --voz` (forte só se instalada; senão use leve e avise) |
| `legenda` | nome de estilo (`corta estilos`) ou `nenhuma` | `creator-bold` | `legendar --estilo` |
| `legenda.ajustes` | `chave=valor` | — | `legendar --ajuste chave=valor` (um por ajuste) |
| `movimento.zoom` | `nao`, `leve`, `normal`, `forte` | `nao` | `montar --zoom` |
| `movimento.enquadrar` | `rosto`, `centro`, `desfocado`, `tela-camera` | `rosto` | `montar --enquadrar` |
| `acabamento.gancho` | `sugerir`, `"texto"`, `nao` | `nao` | `legendar --gancho` |
| `acabamento.cta` | `sugerir`, `"texto"`, `nao` | `nao` | `legendar --cta` + `--cta-em` |
| `acabamento.barra` | `sim`, `nao` | `nao` | `legendar --barra` |
| `acabamento.sons` | `nao`, `poucos`, `todos` | `nao` | `legendar --sons` |
| `cortes` | `quantidade=N · duracao=25-60` | `quantidade=5 · duracao=25-90` | só no formato cortes |
| `aprovacao` | `conteudo`, `etapa`, `direto` | `conteudo` | ver abaixo |
| `idioma` | `pt`, `en`, `es` | `pt` | `--idioma` |
| `videos` | caminhos | pedir para arrastar | — |

## Aprovação
- `conteudo` (padrão): pare para a pessoa aprovar **takes**, **lista de cortes**, **gancho/CTA** e a
  **prévia da legenda**. O resto segue sozinho.
- `etapa`: pare também depois de cada etapa (silêncio, montagem, legenda) mostrando o resultado.
- `direto`: decida tudo pelos critérios das referências e só mostre no fim, com a lista do que decidiu.

## gancho=sugerir / cta=sugerir
Leia o texto do vídeo e proponha 2–3 opções curtas (gancho: até ~10 palavras, fala com quem assiste e
complementa — não repete — a primeira frase; formato `pergunta | resposta` dá 2 níveis). CTA de anúncio
no Meta: "Toque em Saiba mais" (o link é o botão, nunca "link na descrição"). O `--cta-em` é o segundo
em que a fala da chamada começa (ache na transcrição); sem fala de chamada, use o padrão (4 s antes do fim).
