$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = Join-Path $root "apps\desktop"

Push-Location $desktop
try {
    if (-not (Test-Path -LiteralPath "node_modules")) {
        npm install
    }
    npm start
} finally {
    Pop-Location
}
