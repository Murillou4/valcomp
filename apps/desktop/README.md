# Valcomp Companion Windows

Aplicativo Electron portable usado uma vez no computador em que o usuario joga
VALORANT. Ele detecta a sessao Riot local e conclui o vinculo iniciado pelo app
mobile usando um codigo de seis digitos.

## Desenvolvimento

```powershell
npm ci
npm start
```

## Build

Na raiz do repositorio:

```powershell
.\tools\build_companion_windows.ps1
```

O resultado e um unico `dist\Valcomp Companion.exe`. Tokens Riot ficam somente
na memoria do processo principal. Logs sanitizados ficam em
`%APPDATA%\Valcomp Companion\logs`.

O aviso do Windows SmartScreen so pode ser removido de forma consistente com
um certificado confiavel de assinatura de codigo. O executavel beta nao e
assinado.
