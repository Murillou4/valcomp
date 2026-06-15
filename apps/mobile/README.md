# Valcomp Mobile

App Expo/React Native do Valcomp. Esta pasta nasceu com:

```powershell
npx create-expo-app@latest apps/mobile --template default@sdk-56 --no-install --no-agents-md --yes
```

## Rodar

```powershell
cd apps/mobile
npm install
npm run android
```

Para web:

```powershell
npm run web
```

## Ambiente

Copie `.env.example` para `.env.local` durante desenvolvimento:

```powershell
Copy-Item .env.example .env.local
```

Variaveis principais:

- `EXPO_PUBLIC_API_BASE_URL`: URL do FastAPI.
- `EXPO_PUBLIC_DEV_AUTH_TOKEN`: token dev no formato `dev:mobile-user`.
- `EXPO_PUBLIC_EAS_PROJECT_ID`: project id do EAS, usado para gerar ExpoPushToken.
- `EXPO_PUBLIC_SUPABASE_URL`: projeto Supabase.
- `EXPO_PUBLIC_SUPABASE_ANON_KEY`: anon key do app mobile.

## Telas iniciais

- `src/app/index.tsx`: loja diaria, rota mais importante do app.
- `src/app/link.tsx`: gera codigo one-time para o Valcomp Companion no Windows.
- `src/app/account.tsx`: perfil do app e conta Riot vinculada.

## Notificacoes

`src/lib/push.ts` usa `expo-notifications` para pedir permissao, gerar
`ExpoPushToken` e registrar o dispositivo em `POST /notifications/devices`.
Para funcionar em aparelho real, configure `EXPO_PUBLIC_EAS_PROJECT_ID` e as
credenciais de push do projeto Expo/EAS.

## Regra de arquitetura

Enquanto o Supabase Auth mobile nao estiver implementado, chamadas usam o token dev
centralizado em `src/lib/api.ts`. Quando o login real entrar, altere ali para
usar o JWT Supabase da sessao atual.
