# /corta

Receitas de edição de vídeo para o Claude Code. Você monta a edição no app, copia a receita e cola
no Claude Code: ele tira silêncio e erros de fala, legenda no estilo que você escolheu e confere o
resultado. Funciona no Mac e no Windows.

**Estado:** em construção (Fase 1: motor de edição). Ainda não está pronto para instalar.

| Pasta | O que é |
|---|---|
| `plugins/corta/motor` | Motor de edição em Python (comandos `corta preparar`, `montar`, `legendar`, `verificar`…). Ver o README de lá. |
| `plugins/corta/catalogo/legendas` | Estilos de legenda (um arquivo por estilo). |
| `plugins/corta/assets` | Fontes de licença aberta e o vídeo de amostra usado no teste da instalação. |
| `.github/workflows` | Teste automático no Mac e no Windows a cada mudança. |
