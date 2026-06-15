$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = Join-Path $root "apps\desktop"
$release = Join-Path $desktop "release\Valcomp Companion.exe"
$output = Join-Path $root "dist\Valcomp Companion.exe"

Push-Location $desktop
try {
    if (Test-Path -LiteralPath (Join-Path $desktop "package-lock.json")) {
        npm ci
    } else {
        npm install
    }
    npm run dist
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $release)) {
    throw "O electron-builder não gerou o executável esperado: $release"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
Copy-Item -LiteralPath $release -Destination $output -Force

Write-Host "Build Electron portátil gerado em: $output"
