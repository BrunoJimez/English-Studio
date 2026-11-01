$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
$studioDesktop = [Environment]::GetFolderPath('Desktop')
$studioShell = New-Object -ComObject WScript.Shell
$studioShortcut = $studioShell.CreateShortcut((Join-Path $studioDesktop 'English Studio.lnk'))
$studioShortcut.TargetPath = Join-Path $studioRoot '.venv\Scripts\pythonw.exe'
$studioShortcut.Arguments = '"' + (Join-Path $studioRoot 'launch.py') + '"'
$studioShortcut.WorkingDirectory = $studioRoot
$studioShortcut.Description = 'Aprenda ingles com seus filmes e videos. Processamento local.'
$studioIcon = Join-Path $studioRoot 'static\icon.ico'
if (Test-Path -LiteralPath $studioIcon) { $studioShortcut.IconLocation = $studioIcon }
$studioShortcut.WindowStyle = 7
$studioShortcut.Save()
Write-Host ('Atalho criado: ' + (Join-Path $studioDesktop 'English Studio.lnk'))
