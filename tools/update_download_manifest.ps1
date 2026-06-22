param(
  [string]$DocsDir = (Join-Path $PSScriptRoot "..\docs")
)

$ErrorActionPreference = "Stop"

$downloadsDir = Join-Path $DocsDir "downloads"
$manifestPath = Join-Path $downloadsDir "manifest.json"

if (-not (Test-Path -LiteralPath $manifestPath)) {
  throw "Manifest not found: $manifestPath"
}

$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json

function Update-Artifact {
  param(
    [Parameter(Mandatory = $true)] [object]$Artifact
  )

  $artifactPath = Join-Path $downloadsDir $Artifact.file
  if (-not (Test-Path -LiteralPath $artifactPath)) {
    throw "Artifact not found: $artifactPath"
  }

  $file = Get-Item -LiteralPath $artifactPath
  $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $artifactPath

  $Artifact.size_bytes = $file.Length
  $Artifact.sha256 = $hash.Hash
}

$manifest.generated_at = Get-Date -Format "yyyy-MM-dd"
Update-Artifact -Artifact $manifest.mobile
Update-Artifact -Artifact $manifest.desktop

$json = $manifest | ConvertTo-Json -Depth 8 -Compress
$node = Get-Command node -ErrorAction SilentlyContinue

if ($node) {
  $json = ($json | & $node.Source -e "let data=''; process.stdin.on('data', chunk => data += chunk); process.stdin.on('end', () => process.stdout.write(JSON.stringify(JSON.parse(data), null, 2)));") -join [Environment]::NewLine
} else {
  $json = $manifest | ConvertTo-Json -Depth 8
}

[System.IO.File]::WriteAllText($manifestPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Output "Updated $manifestPath"
Write-Output "Mobile:  $($manifest.mobile.file) $($manifest.mobile.size_bytes) $($manifest.mobile.sha256)"
Write-Output "Desktop: $($manifest.desktop.file) $($manifest.desktop.size_bytes) $($manifest.desktop.sha256)"
