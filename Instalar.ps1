$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Preparando o English Studio...' -ForegroundColor Green
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.11 ou superior e tente novamente.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias. Verifique sua conexao.' }
& (Join-Path $PSScriptRoot 'scripts\Create-Shortcut.ps1')
Write-Host 'Pronto. Abra English Studio na area de trabalho.' -ForegroundColor Green
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Host 'FFmpeg ainda precisa ser instalado e incluido no PATH.' -ForegroundColor Yellow }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Host 'Instale Ollama para usar o professor e as traducoes: https://ollama.com/download' -ForegroundColor Yellow }
