param(
    [string]$ApiUrl = "https://valcomp-api-cda2.fly.dev",
    [int]$Limit = 1000,
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$token = $env:VALCOMP_JOB_TOKEN

if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Defina VALCOMP_JOB_TOKEN nesta sessão antes de baixar os diagnósticos."
}

if ([string]::IsNullOrWhiteSpace($Output)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $Output = Join-Path $root "diagnostics\valcomp-diagnostics-$stamp.jsonl"
}

$directory = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $directory | Out-Null

$url = "$($ApiUrl.TrimEnd('/'))/jobs/diagnostics/export?limit=$Limit"
$response = Invoke-RestMethod -Method Get -Uri $url -Headers @{
    "X-Job-Token" = $token
    "Accept" = "application/json"
}

$response.events |
    ForEach-Object { $_ | ConvertTo-Json -Depth 12 -Compress } |
    Set-Content -LiteralPath $Output -Encoding utf8

Write-Host "Diagnósticos salvos em: $Output"
Write-Host "Eventos: $($response.events.Count)"
