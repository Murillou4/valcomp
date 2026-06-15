$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) {
    throw "Defina DATABASE_URL no ambiente."
}
if (-not $env:APP_SECRET_KEY) {
    throw "Defina APP_SECRET_KEY no ambiente."
}
if (-not $env:JOB_SECRET_TOKEN) {
    throw "Defina JOB_SECRET_TOKEN no ambiente."
}

flyctl secrets set `
    --app valcomp-api-cda2 `
    DATABASE_URL="$env:DATABASE_URL" `
    DATABASE_SSL=true `
    APP_SECRET_KEY="$env:APP_SECRET_KEY" `
    JOB_SECRET_TOKEN="$env:JOB_SECRET_TOKEN"

Write-Host "Secrets privados enviados para valcomp-api-cda2."

