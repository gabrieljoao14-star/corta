---
name: editar
description: >-
  Edita vídeos falados a partir de uma receita do /corta — tira silêncio e erros de fala, legenda em estilos do CapCut, zoom no rosto, cortes de vídeo longo, gancho, CTA, barra de progresso e sons — e confere o resultado. Use quando a pessoa colar uma receita que começa com "/corta:editar" ou "receita: corta/", ou pedir para editar, legendar, tirar silêncio, tirar erros de fala, fazer cortes/shorts/reels de um vídeo com o /corta.
---

# /corta — editar a partir da receita

Você conduz a edição; quem corta, legenda e confere é o **motor** do plugin. **Nunca escreva comandos de
ffmpeg na mão nem edite vídeo de outro jeito**: rode só os comandos do motor. Eles já foram testados no
Mac e no Windows e conferem o próprio trabalho.

## Como chamar o motor
A pasta do plugin é a pasta **duas acima desta skill** (o "Base directory" desta skill termina em
`skills/editar`). Chame sempre o lançador com o caminho completo e entre aspas:

```bash
"<PLUGIN>/bin/corta" <comando> …
```

Exemplo: se a skill está em `/Users/ana/.claude/plugins/cache/corta/corta/0.5.0/skills/editar`, o motor é
`"/Users/ana/.claude/plugins/cache/corta/corta/0.5.0/bin/corta"`. No Windows o mesmo lançador roda no
Bash do Claude Code. Caminhos de vídeo sempre entre aspas (têm espaço e acento).

**Antes de tudo**, rode `"<PLUGIN>/bin/corta" --version`. Se falhar, diga à pessoa para rodar
`/corta:instalar` e pare.

## 1. Ler a receita
O formato está em [referencias/receita.md](referencias/receita.md). Campos que faltarem usam o padrão de lá.
Se não houver vídeo na receita, peça para a pessoa **arrastar o arquivo para a conversa** (o Claude Code
cola o caminho). Confira que cada arquivo existe antes de começar.

Diga em 2–3 linhas o que vai fazer e quanto tempo leva (tabela de tempos em
[referencias/comandos.md](referencias/comandos.md)). Vídeo de mais de ~8 min ou transcrição/montagem que
passe de 10 min: rode o comando **em segundo plano** e acompanhe; não deixe o comando estourar o tempo.

## 2. Escolher o fluxo
- `formato: cortes` (live, aula, podcast → vários vídeos curtos): siga [referencias/cortes.md](referencias/cortes.md).
- Qualquer outro formato (um vídeo falado vira um vídeo editado): siga [referencias/video-falado.md](referencias/video-falado.md).
- Só legenda/acabamento num vídeo já pronto (`limpeza: silencio=nao · erros-de-fala=nao`): pule direto
  para `legendar` (ele transcreve sozinho).

## 3. Regras que valem sempre
1. **Nunca sobrescreva** o original nem uma saída anterior (o motor já cria `nome (2).mp4`). Não apague
   vídeos da pessoa.
2. **Decisão de conteúdo é da pessoa**: quais takes ficam, quais trechos viram corte, texto do gancho e do
   CTA, correção de nome próprio. Mostre a lista e espere o "ok" — a não ser que a receita diga
   `aprovacao: direto`. O que é técnico (sincronia, volume, posição) você confere sozinho.
3. **Mostre antes de gravar o vídeo inteiro**: rode `previa`, abra a imagem (Read) e olhe você mesmo antes
   de mostrar. Legenda cobrindo o rosto, palavra cortada na borda ou texto ilegível: ajuste antes.
4. **Confira no fim** com `verificar` e conte o resultado com honestidade: `OK ✅`, `OK com avisos`
   (explique cada aviso) ou `ATENÇÃO` (não entregue como pronto: investigue e corrija).
5. Transcrição erra nomes e termos técnicos: leia o texto antes de legendar e corrija com `corrigir`
   (nome de pessoa/marca na dúvida: pergunte).
6. Fale com a pessoa em português simples. Nada de jargão técnico na conversa.
7. No fim, diga onde estão os arquivos e que a pasta `_corta` ao lado do vídeo guarda os dados da edição
   (pode apagar depois de aprovar, mas sem ela não dá para fazer ajustes rápidos).

## 4. Ajustes depois da entrega
Pedidos como "troca o take do final", "corrige a palavra X", "legenda amarela", "tira o gancho": refaça só
a etapa necessária com os dados que já estão em `_corta` (não transcreva de novo). Ex.: mudar a cor da
legenda = só `legendar` de novo com `--ajuste destaque=#…`.

Se algo do motor falhar de um jeito que você não entende, rode `"<PLUGIN>/bin/corta" diagnostico` e siga o
que ele disser.
