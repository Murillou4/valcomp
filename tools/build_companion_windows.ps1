$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install --upgrade pip
}

& $python -m pip install -e "${root}[desktop]"
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "Valcomp Companion" `
    --add-data "$root\valcomp_companion\assets;valcomp_companion\assets" `
    "$root\valcomp_companion\app.py"

Write-Host "Build gerado em: $root\dist\Valcomp Companion"

