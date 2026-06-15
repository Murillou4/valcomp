# Valcomp Project Guide

Este arquivo e o mapa do projeto. Leia antes de alterar qualquer parte do repo.

## O que existe aqui

O Valcomp tem tres apps:

1. **Backend hospedado**
   - Pasta/pacote: `ares_backend/`
   - Runtime: FastAPI + Supabase + endpoints internos Riot.
   - Deploy: Fly.io via `Dockerfile` e `fly.toml`.
   - Comando local: `.\.venv\Scripts\python.exe -m ares_backend`
   - Responsabilidade: expor login/senha via `/auth/signup`, `/auth/login` e `/auth/refresh` usando Supabase Auth por baixo, guardar perfil, guardar vinculo Riot criptografado, consultar loja diaria, inventario, carteira, itens, status e rotas Valorant remotas.
   - Tambem registra dispositivos push, watchlist de skins desejadas e notificacoes quando uma skin aparece na loja diaria ou Mercado Noturno.
   - Persistencia de producao: preferir `DATABASE_URL` direto do Supabase Postgres. `SUPABASE_SERVICE_ROLE_KEY` e opcional.
   - Nunca deve depender de Riot Developer API key.
   - Nunca deve tentar chamar endpoints `127.0.0.1`, chat local, WebSocket local, XMPP continuo ou rotas que exigem partida/party ao vivo. Para isso retorna resposta estruturada.

2. **Companion Windows**
   - Pacote UI: `valcomp_companion/`
   - CLI reaproveitada: `ares_backend/companion.py`
   - Runtime: Python + PySide6.
   - Comando dev: `.\run-companion.ps1`
   - Build `.exe`: `.\tools\build_companion_windows.ps1`
   - Responsabilidade: rodar uma vez no PC do usuario, detectar Riot Client local, ler sessao/SSID sem mostrar segredos, receber o codigo de 6 digitos do mobile e completar `POST /riot/link/complete`.
   - Depois do vinculo, o usuario pode fechar o app. Ele so precisa abrir de novo se o backend retornar `relink_required`.

3. **Mobile app**
   - Pasta: `apps/mobile/`
   - Runtime: Expo SDK 56 + React Native + Expo Router.
   - Comandos:
     - `cd apps/mobile`
     - `npm install`
     - `npm run android`
     - `npm run web`
   - Responsabilidade: login email/senha pelo backend, foto/avatar, gerar codigo de vinculo, mostrar loja diaria, configurar alertas de skin, carteira, inventario, itens/status e perfil Riot.
   - Estado atual: usa sessao real persistida em `expo-secure-store`; nao use OAuth nem `dev:mobile-user` no APK de producao.

4. **GitHub Pages / downloads**
   - Pasta: `docs/`
   - Downloads publicados: `docs/downloads/valcomp-mobile.apk` e `docs/downloads/valcomp-companion-windows.exe`.
   - Responsabilidade: ensinar o usuario final a instalar o APK, abrir o companion Windows e vincular a Riot pelo codigo.

## Fluxo de vinculo correto

1. Usuario cria conta ou entra no mobile com email/senha pelo backend.
2. Mobile chama `POST /riot/link/start` com JWT Supabase.
3. Backend gera `link_code` de 6 digitos com TTL curto.
4. Usuario abre Valcomp Companion no Windows.
5. Companion detecta Riot Client/VALORANT local, le tokens/SSID e envia `POST /riot/link/complete`.
6. Backend criptografa credenciais Riot com `APP_SECRET_KEY` e associa ao usuario.
7. Mobile passa a usar endpoints remotos do backend.

## Rotas importantes

Prioridade maxima:

- `GET /valorant/store/daily`
- `GET /valorant/items/{item_id}/status`
- `GET /valorant/store/wallet`
- `GET /valorant/store/inventory`
- `POST /notifications/devices`
- `POST /valorant/skins/watchlist`
- `POST /valorant/skins/watchlist/check`
- `POST /jobs/store-alerts/run`

Rotas de catalogo:

- Fonte: `ares_console/resources/endpoints.json`
- Status atual das 82 rotas:
  - `remote_supported`: pode executar no backend hospedado.
  - `local_only`: so existe no PC do usuario.
  - `requires_game_state`: exige party/pre-game/current-game vivo.
  - `unsafe_mutation`: mutacao bloqueada por padrao.
  - `unsupported_hosted`: ainda nao exposto como API hospedada.

## Visual e assets

Referencia local do Figma:

- `C:\Users\muril\Downloads\Valcomp APP.fig`
- `C:\Users\muril\Downloads\Valcomp APP.zip`
- Export extraido no workspace: `figma-export/`

Assets usados:

- Mobile: `apps/mobile/assets/valcomp/`
- Companion: `valcomp_companion/assets/`

Linguagem visual atual:

- Fundo escuro violeta quase preto.
- Coral/vermelho da marca como acento principal.
- Cards grandes, arredondados, com borda sutil.
- Logo Valcomp e imagem de arma do export Figma.

## Seguranca

- Nunca logar SSID, access token, entitlement token, cookies ou PUUID completo.
- Nunca devolver `expo_push_token` bruto em resposta HTTP. Use somente `masked_token`.
- `APP_SECRET_KEY` e `SUPABASE_SERVICE_ROLE_KEY` so ficam em `.env`/Fly secrets.
- `DATABASE_URL` contem senha do banco e tambem so deve ficar em env/Fly secrets.
- `JOB_SECRET_TOKEN` protege jobs externos, como cron de alertas de loja.
- Companion pode manter tokens em memoria durante o vinculo, mas nao deve salvar em disco.
- Mobile so usa `SUPABASE_ANON_KEY`; service role key nunca entra no app.

## Notificacoes de skin

Fluxo correto:

1. Mobile pede permissao de push e gera `ExpoPushToken`.
2. Mobile registra o token em `POST /notifications/devices`.
3. Usuario escolhe uma skin e chama `POST /valorant/skins/watchlist`.
4. Quando `/valorant/store/daily` e consultada, o backend checa a watchlist e envia push se encontrar match.
5. Para funcionamento automatico, configure um cron externo chamando `POST /jobs/store-alerts/run` com header `X-Job-Token`.
6. O backend grava `notification_deliveries` para nao enviar a mesma skin repetida na mesma rotacao de loja.

O backend envia via Expo Push Service. O mobile precisa de `EXPO_PUBLIC_EAS_PROJECT_ID`
para gerar token com `expo-notifications`.

## Validacao antes de entregar

Backend/Python:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Mobile:

```powershell
cd apps/mobile
npm install
npm run lint
```

Companion:

```powershell
.\.venv\Scripts\python.exe -m compileall ares_backend valcomp_companion
```

## Onde mexer para cada tarefa

- Nova rota backend: `ares_backend/app.py`, `ares_backend/riot.py`, `ares_backend/store.py`.
- Mudanca de classificacao de rotas: `ares_backend/capabilities.py`.
- Auth email/senha e JWT Supabase: `ares_backend/auth.py`.
- Persistencia Supabase: `ares_backend/repository.py` e `supabase/schema.sql`.
- Notificacoes/watchlist: `ares_backend/notifications.py`, `ares_backend/app.py` e `supabase/schema.sql`.
- UI companion: `valcomp_companion/app.py`.
- Logica companion sem UI: `ares_backend/companion.py`.
- Mobile API client: `apps/mobile/src/lib/api.ts`.
- Mobile sessao/login: `apps/mobile/src/lib/session.tsx` e `apps/mobile/src/components/auth-screen.tsx`.
- Mobile telas: `apps/mobile/src/app/`.
- Pagina publica/downloads: `docs/`.
