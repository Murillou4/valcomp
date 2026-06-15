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

- Codigo: `valcomp_companion/`
- Runtime: Python + PySide6.
- Desenvolvimento: `.\run-companion.ps1`
- Build: `.\tools\build_companion_windows.ps1`

O companion roda uma vez no PC em que o usuario joga, detecta a sessao local
Riot, recebe o codigo de seis digitos e completa `/riot/link/complete`. Ele nao
mostra nem salva tokens. Deve ser aberto novamente somente quando o backend
retornar `relink_required`.

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
- Vincular;
- Wishlist/Alertas;
- Conta.

A barra inferior possui apenas Loja, Home e Estatisticas. Alertas e Conta ficam
no header; Vincular aparece nos estados sem conta Riot ou pela tela Conta.

## 4. GitHub Pages

- Pagina: `docs/`
- APK: `docs/downloads/valcomp-mobile.apk`
- Companion: `docs/downloads/valcomp-companion-windows.exe`
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
- Mutacoes Riot ficam bloqueadas por padrao.
- Rotas locais/chat/party ao vivo retornam status estruturado no backend.

## Validacao

```powershell
python -m pytest
python -m compileall -q ares_backend valcomp_companion

cd apps/mobile
flutter analyze
flutter test
flutter build apk --release
```

Arquivos por responsabilidade:

- API: `ares_backend/app.py`
- Riot remoto: `ares_backend/riot.py`
- Loja: `ares_backend/store.py`
- Assets: `ares_backend/assets.py`
- Player normalizado: `ares_backend/player.py`
- Push/wishlist: `ares_backend/notifications.py`
- Banco: `ares_backend/repository.py`, `supabase/schema.sql`
- Mobile: `apps/mobile/lib/`
- Companion: `valcomp_companion/app.py`
