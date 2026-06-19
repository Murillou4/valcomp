# Valcomp Project Guide

Leia este arquivo antes de alterar o repositorio. O Valcomp tem tres aplicativos
e uma pagina publica.

## 1. Backend

- Codigo: `ares_backend/`
- Runtime: FastAPI + Supabase Auth/Postgres + endpoints internos Riot.
- Producao: `https://valcomp-api-cda2.fly.dev`
- Deploy: `Dockerfile` + `fly.toml`.
- Nao usa Riot Developer API key.

Responsabilidades:

- login, cadastro e refresh em `/auth/signup`, `/auth/login` e `/auth/refresh`;
- perfil do app e vinculo Riot criptografado;
- loja diaria, Mercado Noturno, carteira, inventario, itens e status;
- rank/RR e historico normalizado em `/valorant/player/summary`;
- wishlist, dispositivos FCM e entregas de notificacao.

Nunca invente campos do jogo. Antes de criar UI ou normalizadores, confira
`ares_backend/app.py`, os testes e a resposta real da Riot/Valorant-API.

## 2. Companion Windows

- Codigo atual: `apps/desktop/`
- Runtime: Electron, com Node.js apenas no processo principal e
  `contextIsolation` no renderer.
- Desenvolvimento: `.\run-companion.ps1`
- Build: `.\tools\build_companion_windows.ps1`

O Companion 2 roda na bandeja, detecta a sessao local Riot, publica estado
sanitizado em `/ws/companion` e executa apenas comandos tipados. O pareamento
ao vivo e separado do vinculo Riot e usa segredo protegido por `safeStorage`.
Tokens Riot continuam somente na memoria do processo principal.

O artefato de distribuicao deve continuar sendo um unico
`Valcomp Companion.exe`, no formato portable do `electron-builder`. A pasta
`valcomp_companion/` e o companion Python antigo sao legado e nao devem receber
novas features.

## 3. Mobile Flutter

- Codigo: `apps/mobile/`
- Runtime: Flutter/Dart.
- Pacote Android: `com.cda2.valcomp`
- API padrao: `https://valcomp-api-cda2.fly.dev`

Comandos:

```powershell
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

Build:

```powershell
$env:GRADLE_USER_HOME = "E:\DevCaches\gradle"
flutter build apk --release
```

A chave Android fica fora do Git:

- `E:\DevSecrets\valcomp-upload.jks`
- `E:\DevSecrets\valcomp-upload-key.txt`
- `apps/mobile/android/key.properties` e ignorado.

Telas:

- autenticar;
- Home;
- Loja diaria/Mercado Noturno;
- Estatisticas;
- detalhes completos de partidas e skins;
- Vincular;
- Wishlist/Alertas;
- Conta.

A barra inferior possui Loja, Home, Estatisticas e Partida. A pagina Partida
acompanha lobby, fila, pre-game e partida usando apenas snapshots reais do
Companion; Alertas e Conta continuam no header.

## 4. Live Companion

- Pareamento: `/companion/pair/start` e `/companion/pair/complete`.
- Desktop: `/ws/companion` com segredo de dispositivo e heartbeat de 10 s.
- Mobile: `/ws/live` autenticado pela sessao Valcomp.
- Estado duravel: `live_snapshots`; comandos: `live_commands`.
- Nunca encaminhar payload Riot bruto, token, PUUID ou URL arbitraria.
- `match.accept` permanece desligado ate validacao real do Swagger local.
- A feature e experimental e nao aprovada pela Riot.

## 5. GitHub Pages

- Pagina: `docs/`
- APK: `docs/downloads/valcomp-mobile.apk`
- Companion: `docs/downloads/valcomp-companion-windows-2.0.1.exe`
- Manifesto: `docs/downloads/manifest.json`

## Fluxo de vinculo

1. Mobile autentica no backend.
2. Mobile chama `POST /riot/link/start`.
3. Backend gera um codigo de seis digitos com validade curta.
4. Usuario abre o companion no PC com Riot Client/VALORANT logado.
5. Companion envia a sessao para `POST /riot/link/complete`.
6. Backend criptografa a sessao Riot com `APP_SECRET_KEY`.
7. Mobile passa a consultar as rotas privadas.

## Loja e dados reais

Rotas prioritarias:

- `GET /valorant/store/daily`
- `GET /valorant/store/night-market`
- `GET /valorant/items/{category}`
- `GET /valorant/items/{item_id}/status`
- `GET /valorant/player/summary`
- `GET /valorant/player/matches/{match_id}`
- `GET /valorant/skins/watchlist`

Valorant-API fornece assets publicos. Loja, conta, rank e historico privados vem
da sessao Riot vinculada. Loja diaria nao existe na Riot Developer API oficial.

## Push de skins

1. Flutter solicita permissao e gera token Firebase Cloud Messaging.
2. Mobile registra `push_token` com `provider=fcm`.
3. Usuario adiciona uma skin em `/valorant/skins/watchlist`.
4. Backend compara a wishlist com a loja.
5. Firebase Admin envia a notificacao e `notification_deliveries` evita spam.

`POST /notifications/test` envia um teste somente aos aparelhos FCM do usuario
autenticado e e usado pelo botao da tela Alertas.

O app Android usa a configuracao publica gerada pelo FlutterFire em
`apps/mobile/lib/firebase_options.dart` e
`apps/mobile/android/app/google-services.json`. O backend recebe
`FIREBASE_PROJECT_ID` e `FIREBASE_SERVICE_ACCOUNT_JSON` como secrets no Fly.
A chave privada nunca entra no Git.

Para checagem automatica, um cron chama:

```text
POST /jobs/store-alerts/run
X-Job-Token: <JOB_SECRET_TOKEN>
```

## Seguranca

- Nunca logar SSID, access token, entitlement, cookies ou PUUID completo.
- Service role, senha Postgres, chave Firebase e chave Android nao entram no Git.
- Companion nao persiste a sessao Riot em disco.
- Logs locais e remotos passam por sanitizacao antes de serem gravados.
- Mutacoes Riot ficam bloqueadas por padrao.
- Rotas locais/chat/party ao vivo retornam status estruturado no backend.

## Diagnosticos

- Backend: eventos sanitizados em `diagnostic_events`, JSON estruturado no
  stdout do Fly e `GET /jobs/diagnostics/export`.
- Mobile: JSONL rotativo no armazenamento do app, envio sanitizado para
  `POST /diagnostics/events` e copia pela tela Conta.
- Desktop: JSONL rotativo em `%APPDATA%\Valcomp Companion\logs`, com botoes para
  copiar o relatorio ou abrir a pasta.
- Coleta administrativa: `.\tools\pull_diagnostics.ps1`.

## Validacao

```powershell
python -m pytest
python -m compileall -q ares_backend

cd apps/mobile
flutter analyze
flutter test
flutter build apk --release

cd ..\desktop
npm audit
npm run dist
```

Arquivos por responsabilidade:

- API: `ares_backend/app.py`
- Riot remoto: `ares_backend/riot.py`
- Loja: `ares_backend/store.py`
- Assets: `ares_backend/assets.py`
- Player normalizado: `ares_backend/player.py`
- Diagnosticos: `ares_backend/diagnostics.py`
- Push/wishlist: `ares_backend/notifications.py`
- Banco: `ares_backend/repository.py`, `supabase/schema.sql`
- Mobile: `apps/mobile/lib/`
- Companion: `apps/desktop/src/`
