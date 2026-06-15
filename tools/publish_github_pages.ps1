param(
    [string]$Owner = "cda2",
    [string]$Repo = "valcomp",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"

$fullName = "$Owner/$Repo"
$remoteUrl = "https://github.com/$fullName.git"

gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI nao autenticado. Rode: gh auth login"
}

if (-not (Test-Path -LiteralPath ".git")) {
    git init -b main
}

$repoExists = $true
gh repo view $fullName *> $null
if ($LASTEXITCODE -ne 0) {
    $repoExists = $false
}

if ($repoExists) {
    if (git remote get-url origin *> $null) {
        git remote set-url origin $remoteUrl
    } else {
        git remote add origin $remoteUrl
    }
    git push -u origin main
} else {
    $visibilityFlag = "--$Visibility"
    gh repo create $fullName $visibilityFlag --source . --remote origin --push
}

$payload = @{
    source = @{
        branch = "main"
        path = "/docs"
    }
} | ConvertTo-Json -Depth 4

$payload | gh api --method POST "repos/$fullName/pages" --input - *> $null
if ($LASTEXITCODE -ne 0) {
    $payload | gh api --method PUT "repos/$fullName/pages" --input - *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel configurar GitHub Pages para $fullName."
    }
}

Write-Host "Publicado. Pages: https://$Owner.github.io/$Repo/"
