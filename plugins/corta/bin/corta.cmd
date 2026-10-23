@echo off
rem Lançador do motor do /corta para o Prompt de Comando do Windows.
setlocal
set "UV="
for /f "delims=" %%i in ('where uv 2^>nul') do if not defined UV set "UV=%%i"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
  echo O /corta ainda nao foi instalado neste computador ^(falta o uv^). Rode: /corta:instalar
  exit /b 1
)
set PYTHONUTF8=1
"%UV%" run --quiet --frozen --project "%~dp0..\motor" corta %*
