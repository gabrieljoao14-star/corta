---
name: diagnostico
description: >-
  Descobre por que o /corta não está funcionando neste computador e conserta — confere uv, ffmpeg, bibliotecas, arquivos do plugin, espaço em disco, modelo de transcrição e permissões, e diz o que fazer em português simples. Use quando um comando do /corta falhar, quando a pessoa disser que o /corta "deu erro" ou "não funciona", ou para mandar um relatório ao suporte.
---

# /corta — diagnóstico

A pasta do plugin é a pasta **duas acima desta skill** (o "Base directory" termina em
`skills/diagnostico`). Chame-a de `<PLUGIN>`.

1. Rode `"<PLUGIN>/bin/corta" diagnostico`.
   - Se o próprio lançador falhar dizendo que falta o `uv`: o /corta não foi instalado neste computador —
     siga a skill `/corta:instalar`.
2. Leia cada linha: ✅ está ok; ❌ vem com uma seta `→` dizendo o conserto.
3. Conserte o que der sem pedir nada à pessoa:
   - "rode o instalador de novo" → siga `/corta:instalar` (é seguro repetir);
   - arquivos do plugin faltando → `claude plugin update corta` e depois `/corta:instalar`;
   - modelo de transcrição "ainda não baixado" não é erro: baixa sozinho na primeira edição.
4. O que precisa da pessoa, explique em uma frase o que ela faz:
   - pouco espaço em disco → quanto liberar (mínimo 10 GB);
   - vídeo no OneDrive/iCloud "só na nuvem" → baixar o arquivo para o computador;
   - sem permissão de escrita → onde está o problema.
5. Rode o diagnóstico de novo para confirmar. Se tudo der ✅ e o erro original continuar, rode
   `"<PLUGIN>/bin/corta" amostra` (edita o vídeo de teste): se a amostra passar, o problema é no vídeo da
   pessoa (arquivo corrompido, sem som, formato estranho) — diga isso e peça outro arquivo ou um trecho.
6. Para o suporte: o relatório completo fica em `~/.corta/diagnostico.json`. Mostre o caminho se a pessoa
   precisar mandar.
