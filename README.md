# Ares Console

> Novo mapa do projeto: leia `PROJECT_GUIDE.md` antes de mexer no backend,
> companion Windows ou app mobile Expo.

## Estado atual do Valcomp

- Backend em producao: `https://valcomp-api-cda2.fly.dev`.
- Auth do app: email/senha pelo proprio backend em `/auth/signup`, `/auth/login`
  e `/auth/refresh`, usando Supabase Auth por baixo. OAuth Google/GitHub ficou
  fora por enquanto.
- Mobile Android: APK gerado em `docs/downloads/valcomp-mobile.apk`.
- Companion Windows: executavel unico em `docs/downloads/valcomp-companion-windows.exe`.
- Pagina publica para GitHub Pages: `docs/index.html`.
- O app mobile nao deve depender de `dev:mobile-user` em producao.

Cliente desktop moderno em Python para explorar as APIs não oficiais usadas pelo
cliente do VALORANT. O catálogo inclui as 82 operações documentadas em
[valapidocs.techchrism.me](https://valapidocs.techchrism.me), incluindo HTTP,
WebSocket local e XMPP.

## Recursos

- Interface Qt 6/QML escura, responsiva e com busca por rota, método ou URL.
- Leitura automática do lockfile local do Riot Client.
- Detecção de token, entitlement, PUUID, região, shard e versão do cliente.
- Preenchimento automático de IDs de party, pre-game e partida atual quando disponíveis.
- Headers Riot injetados automaticamente sem expor tokens na interface.
- Cookies persistentes para os endpoints de autenticação.
- Editor de variáveis, query params, JSON, headers extras e resposta formatada.
- Confirmação antes de executar `POST`, `PUT`, `PATCH` ou `DELETE`.
- WebSocket local com assinatura automática de `OnJsonApiEvent`.
- XMPP direto por TLS com autenticação RSO/PAS e envio de XML bruto.

## Executar

No PowerShell:

```powershell
.\run.ps1
```

O script cria `.venv`, instala as dependências e abre o aplicativo. Para preparar
o ambiente manualmente:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ares_console
```

O Riot Client precisa estar aberto e com uma sessão autenticada. Algumas rotas
também exigem que o VALORANT esteja em uma fase específica, como party, seleção
de agente ou partida.

## Segurança

- Tokens, entitlement e senha do lockfile ficam apenas na memória.
- O aplicativo não grava credenciais em arquivos.
- Headers sensíveis e `Set-Cookie` são ocultados no painel de resposta.
- Certificados inválidos só são aceitos nas conexões locais em `127.0.0.1`.
- APIs remotas continuam usando validação TLS normal.

Esses endpoints não são oficiais nem possuem garantia de estabilidade. Use
operações mutáveis com cuidado e respeite os termos da Riot Games.

## Atualizar o catálogo

O arquivo `ares_console/resources/endpoints.json` é gerado mecanicamente a partir
do pacote `valorant-api-types` do projeto de documentação:

```powershell
node tools/export_catalog.mjs `
  "C:\caminho\para\valorant-api-docs\valorant-api-types" `
  "ares_console\resources\endpoints.json"
```

Antes disso, execute `npm ci` e `npm run build` dentro de
`valorant-api-types`.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Fonte do catálogo:
[techchrism/valorant-api-docs](https://github.com/techchrism/valorant-api-docs).

## Backend FastAPI para mobile

Este repositorio tambem inclui `ares_backend`, uma API FastAPI pensada para app
mobile com Supabase Auth/Postgres/Storage e sem Riot Developer API key. O app
mobile autentica no Supabase e envia `Authorization: Bearer <supabase_jwt>` para
o backend.

Principais rotas:

- `POST /auth/session/verify`
- `POST /riot/link/start`
- `POST /riot/link/complete`
- `GET /me` e `PATCH /me`
- `GET /valorant/routes`
- `POST /valorant/routes/{route_id}`
- `GET /valorant/store/daily`
- `GET /valorant/store/wallet`
- `GET /valorant/store/inventory`
- `GET /valorant/store/offers`
- `GET /valorant/store/night-market`
- `GET /valorant/store/bundles`
- `GET /valorant/items/{category}` para `weapons`, `skins`, `skin-levels`,
  `chromas`, `buddies`, `cards` e `titles`
- `GET /valorant/items/{item_id}/status`
- `GET /valorant/player/profile`, `/mmr`, `/matches`, `/loadout`, `/xp`,
  `/contracts`, `/item-upgrades` e `/content`
- `POST /notifications/devices`
- `GET /notifications/devices`
- `DELETE /notifications/devices/{device_id}`
- `GET /notifications/deliveries`
- `GET /valorant/skins/watchlist`
- `POST /valorant/skins/watchlist`
- `DELETE /valorant/skins/watchlist/{item_id}`
- `POST /valorant/skins/watchlist/check`
- `POST /jobs/store-alerts/run`

Rotas locais, chat local, WebSocket, XMPP, party/pre-game/current-game ao vivo e
mutacoes perigosas sao classificadas em `/valorant/routes` e retornam resposta
estruturada quando nao podem rodar em backend hospedado.

### Rodar local

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m ares_backend
```

Em desenvolvimento, `ALLOW_DEV_AUTH=true` permite testar com:

```text
Authorization: Bearer dev:mobile-user
```

### Supabase

Execute `supabase/schema.sql` no SQL editor do Supabase. Ele cria `profiles`,
`riot_accounts`, `riot_credentials`, `link_codes`, `store_snapshots`,
`item_cache` e o bucket publico `avatars`.

Variaveis necessarias no backend:

- `APP_SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` ou publishable key
- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` opcional quando `DATABASE_URL` estiver configurado
- `SUPABASE_JWT_SECRET` opcional; sem ele o backend valida JWT pela API Auth do Supabase
- `ALLOW_DEV_AUTH=false` em producao
- `JOB_SECRET_TOKEN` para cron de alertas

### Notificacoes de skin

Para o usuario ser avisado quando uma skin desejada cair na loja:

1. O mobile registra o `ExpoPushToken` em `POST /notifications/devices`.
2. O usuario adiciona a skin em `POST /valorant/skins/watchlist`.
3. O backend checa automaticamente em `GET /valorant/store/daily`.
4. Para checagem sem o usuario abrir o app, configure um cron externo chamando:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://valcomp-api-cda2.fly.dev/jobs/store-alerts/run" `
  -Headers @{ "X-Job-Token" = "<JOB_SECRET_TOKEN>" }
```

O backend grava entregas em `notification_deliveries`, entao a mesma skin nao
gera spam dentro da mesma rotacao de loja.

### Companion Windows

Depois que o app chamar `POST /riot/link/start`, rode no PC onde o Riot Client
esta logado. Para abrir o app visual do companion em desenvolvimento:

```powershell
.\run-companion.ps1
```

Para usar o modo CLI:

```powershell
.\.venv\Scripts\python.exe -m ares_backend.companion `
  --backend-url https://valcomp-api-cda2.fly.dev `
  --code 123456
```

O companion le a sessao Riot local, envia tokens/SSID para o backend pelo codigo
one-time e pode ser fechado. Se a sessao expirar ou MFA bloquear o refresh, a API
retorna `relink_required`.

Para gerar o build Windows:

```powershell
.\tools\build_companion_windows.ps1
```

O executavel unico, com recursos embutidos, fica em `dist\Valcomp Companion.exe`.

### Mobile Expo

O app mobile fica em `apps/mobile`:

```powershell
cd apps/mobile
npm install
npm run android
```

As telas iniciais ja cobrem loja diaria, vinculo por codigo e perfil/conta.

### Fly.io

O deploy usa `Dockerfile` sem instalar a UI Qt pesada:

```powershell
fly apps create valcomp-api-cda2 --org personal
fly secrets set --app valcomp-api-cda2 ENVIRONMENT=production ALLOW_DEV_AUTH=false SUPABASE_URL=... SUPABASE_ANON_KEY=...
.\tools\fly_set_private_secrets.ps1
fly deploy
```

Para aplicar o schema no Supabase sem salvar senha no repo:

```powershell
$env:DATABASE_URL="postgresql://postgres:<senha>@db.<project>.supabase.co:5432/postgres"
.\tools\apply_supabase_schema.ps1
```
