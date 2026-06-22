# Valcomp

Valcomp is a companion app for VALORANT players who want to check the daily
store on mobile, keep a skin wishlist, and get notified when a monitored skin
comes back.

Live page: https://murillou4.github.io/valcomp/

## What ships in this repo

- Public GitHub Pages landing in `docs/`.
- Android Flutter app in `apps/mobile`.
- Windows Electron companion in `apps/desktop`.
- FastAPI backend in `ares_backend`.
- Supabase schema in `supabase/schema.sql`.
- Release artifacts in `docs/downloads/`.

## Current public downloads

| Target | File | Version | Size | SHA-256 |
| --- | --- | --- | --- | --- |
| Android | `valcomp-mobile.apk` | `1.4.0` build `18` | `64.9 MB` | `8AD49BF346209184B269735EDC173AADBFA0C7A46B08B49550E1D651A5F67ED0` |
| Windows | `valcomp-companion-windows-2.1.0.exe` | `2.1.0` | `93.2 MB` | `7C3E95635C06768043E2C28C2B0111870C0EB588B1B4688996C9092A90B7DF11` |

The landing reads `docs/downloads/manifest.json` at runtime and keeps the static
HTML values as fallback. After replacing any download artifact, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\update_download_manifest.ps1
```

## Product flow

1. Install the Android APK.
2. Sign in on mobile.
3. Generate a short pairing code.
4. Open the Windows companion on the PC where Riot Client or VALORANT is logged in.
5. Paste the code and let the backend connect store, wishlist, and alerts.

## Local preview

The Pages site is static. From the repo root:

```powershell
python -m http.server 4173 --directory docs
```

Open:

```text
http://127.0.0.1:4173/
```

Before pushing a landing change, check:

- Desktop width around `1280x720`.
- Mobile width around `390x844`.
- No horizontal overflow.
- Hero, bento, flow, downloads, final CTA, and notes.
- Console has no errors.
- `docs/index.html` references the newest `styles.css?v=...` cache key.

## Backend

Production API:

```text
https://valcomp-api-cda2.fly.dev
```

Important routes:

- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /valorant/store/daily`
- `GET /valorant/store/night-market`
- `POST /valorant/skins/watchlist`
- `POST /valorant/skins/watchlist/check`
- `POST /notifications/devices`
- `POST /companion/pair/start`
- `POST /companion/pair/complete`
- `GET /live/state`
- `WS /ws/companion`
- `WS /ws/live`
- `POST /jobs/store-alerts/run`

Run locally:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m ares_backend
```

Required production variables include:

- `APP_SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `JOB_SECRET_TOKEN`
- `ALLOW_DEV_AUTH=false`

## Windows companion

Development:

```powershell
.\run-companion.ps1
```

Build:

```powershell
.\tools\build_companion_windows.ps1
```

The companion reads the local Riot session, sends the pairing payload to the
backend, and can be closed after linking. It does not ask the user to type Riot
credentials into Valcomp.

## Android app

```powershell
cd apps/mobile
flutter pub get
flutter analyze
flutter run
```

The mobile app covers auth, home, daily store, night market, wishlist, alerts,
stats, match details, account, and companion pairing.

## Release checklist

1. Build Android and Windows artifacts.
2. Copy artifacts into `docs/downloads/`.
3. Update `docs/downloads/manifest.json`:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\tools\update_download_manifest.ps1
   ```

4. Update landing cache keys when CSS changes.
5. Preview locally on desktop and mobile.
6. Run:

   ```powershell
   git diff --check
   ```

7. Commit and push `main`; GitHub Pages serves from `/docs`.

## Security notes

- Valcomp is an independent project and is not affiliated with Riot Games.
- The Windows beta executable is currently unsigned, so SmartScreen can show
  `Unknown publisher`.
- Validate the SHA-256 from the landing before running a downloaded file.
- Riot tokens are handled through the backend/companion flow; do not commit
  secrets, sessions, or `.env` files.

## Public disclaimer

VALORANT is a trademark of Riot Games, Inc. This repository and the Valcomp app
are independent and are not endorsed by Riot Games.
