$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install --upgrade pip
    & $python -m pip install -e "${root}[desktop]"
}

& $python -m ares_console
