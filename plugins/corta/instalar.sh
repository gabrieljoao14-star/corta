#!/usr/bin/env bash
# Instalador do /corta para Mac (e Linux). Não pede senha de administrador:
# o uv vai para ~/.local/bin, o ffmpeg (se faltar) para ~/.corta/bin e o resto fica dentro do plugin.
# No fim edita o vídeo de amostra e só diz "TUDO CERTO" se a conferência passar.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTA_HOME="${CORTA_HOME:-${HOME}/.corta}"
mkdir -p "${CORTA_HOME}/bin"
passo() { printf '\n== %s\n' "$*"; }
erro() { printf '\n❌ %s\n' "$*" >&2; exit 1; }

passo "1/5 uv (cuida do Python sem mexer no resto do computador)"
UV="$(command -v uv 2>/dev/null || true)"
[ -z "${UV}" ] && [ -x "${HOME}/.local/bin/uv" ] && UV="${HOME}/.local/bin/uv"
if [ -z "${UV}" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh || erro "Não consegui baixar o uv. Confira a internet e rode de novo."
  UV="${HOME}/.local/bin/uv"
fi
"${UV}" --version

passo "2/5 ffmpeg (corta e grava o vídeo)"
versao_ok() { local v; v="$("$1" -version 2>/dev/null | head -1 | sed -E 's/^ffmpeg version n?([0-9]+).*/\1/')"; [[ "${v}" =~ ^[0-9]+$ ]] && [ "${v}" -ge 7 ]; }
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && versao_ok "$(command -v ffmpeg)"; then
  echo "usando o ffmpeg do sistema: $(command -v ffmpeg)"
elif [ -x "${CORTA_HOME}/bin/ffmpeg" ] && versao_ok "${CORTA_HOME}/bin/ffmpeg"; then
  echo "usando ${CORTA_HOME}/bin/ffmpeg"
else
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) url="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release" ;;
    Darwin-x86_64) url="https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/release" ;;
    Linux-x86_64) url="https://ffmpeg.martin-riedl.de/redirect/latest/linux/amd64/release" ;;
    Linux-aarch64) url="https://ffmpeg.martin-riedl.de/redirect/latest/linux/arm64/release" ;;
    *) erro "Sistema não suportado: $(uname -s) $(uname -m)" ;;
  esac
  tmp="$(mktemp -d)"
  for prog in ffmpeg ffprobe; do
    echo "baixando ${prog}…"
    curl -fL --progress-bar -o "${tmp}/${prog}.zip" "${url}/${prog}.zip" || erro "Não consegui baixar o ${prog}. Confira a internet e rode de novo."
    unzip -o -q "${tmp}/${prog}.zip" -d "${tmp}" && mv -f "${tmp}/${prog}" "${CORTA_HOME}/bin/${prog}" && chmod +x "${CORTA_HOME}/bin/${prog}"
  done
  rm -rf "${tmp}"
  versao_ok "${CORTA_HOME}/bin/ffmpeg" || erro "O ffmpeg baixado não abriu."
fi

passo "3/5 bibliotecas do motor (Python 3.12, transcrição, detector de rosto)"
extra=()
[ "${CORTA_FORTE:-0}" = "1" ] && extra=(--extra forte)
"${UV}" sync --project "${RAIZ}/motor" --python 3.12 --frozen ${extra[@]+"${extra[@]}"} || erro "A instalação das bibliotecas falhou. Rode de novo; se repetir, rode /corta:diagnostico."

passo "4/5 medindo este computador"
"${RAIZ}/bin/corta" perfil --recalcular

passo "5/5 teste: editando o vídeo de amostra (a 1ª vez baixa o modelo de transcrição, 1–3 GB)"
"${RAIZ}/bin/corta" amostra
