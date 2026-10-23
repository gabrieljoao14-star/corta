# /corta

Receitas de edição de vídeo para o Claude Code. Você monta a edição no app, copia a receita e cola
no Claude Code: ele tira silêncio e erros de fala, legenda no estilo que você escolheu, dá zoom no rosto,
faz cortes de vídeo longo e confere o resultado. Funciona no Mac e no Windows.

## Instalar (uma vez por computador)
Precisa: Claude Code com plano pago, Mac (chip Apple ou Intel) ou Windows 10/11, ~10 GB livres.
Cole isto no Claude Code:

```
Instale o /corta para mim, sem pular nenhum passo e me mostrando o progresso:
1. Rode no terminal: claude plugin marketplace add gabrieljoao14-star/corta
2. Rode: claude plugin install corta@corta
3. Descubra a pasta do plugin com: claude plugin list --json (o caminho de instalação do "corta").
4. Rode o instalador dessa pasta em segundo plano e acompanhe até o fim:
   no Mac: bash "<pasta>/instalar.sh"
   no Windows: powershell -NoProfile -ExecutionPolicy Bypass -File "<pasta>\instalar.ps1"
   Ele baixa o que falta (pode levar de 5 a 20 minutos) e edita um vídeo de teste.
5. Só termine quando aparecer "✅ TUDO CERTO". Se der erro, me explique em português simples o que fazer.
6. No fim, me peça para fechar e abrir o Claude Code.
```

Depois disso, para editar é só colar uma receita do app /corta. Se algo der errado: `/corta:diagnostico`.

## O que tem aqui
| Pasta | O que é |
|---|---|
| `plugins/corta/skills` | As skills do Claude Code: `editar` (lê a receita e conduz), `instalar`, `diagnostico`. |
| `plugins/corta/motor` | Motor de edição em Python (`corta preparar`, `montar`, `legendar`, `cortar`, `verificar`…). |
| `plugins/corta/bin/corta` | Lançador do motor (acha o `uv` e usa as versões travadas). |
| `plugins/corta/instalar.sh` / `instalar.ps1` | Instaladores do Mac e do Windows (sem senha de administrador). |
| `plugins/corta/catalogo/legendas` | Estilos de legenda (um arquivo por estilo). |
| `plugins/corta/assets` | Fontes de licença aberta, detector de rosto (YuNet, MIT) e o vídeo de amostra do teste. |
| `.github/workflows` | Teste automático no Mac e no Windows a cada mudança, incluindo os instaladores. |
