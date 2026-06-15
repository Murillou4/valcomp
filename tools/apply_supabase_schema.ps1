$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not $env:DATABASE_URL) {
    throw "Defina DATABASE_URL no ambiente antes de rodar. Ex: `$env:DATABASE_URL='postgresql://...'"
}

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install --upgrade pip
}

& $python -m pip install -e "$root"

$schemaPath = Join-Path $root "supabase\schema.sql"
$env:SCHEMA_PATH = $schemaPath
@'
import asyncio
import os
import ssl
from pathlib import Path

import asyncpg


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    schema_path = Path(os.environ["SCHEMA_PATH"])
    sql = schema_path.read_text(encoding="utf-8")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(dsn=database_url, ssl=context)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


asyncio.run(main())
'@ | & $python -
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao aplicar schema Supabase."
}

Write-Host "Schema Supabase aplicado com sucesso."
