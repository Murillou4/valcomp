# Valcomp Mobile

Aplicativo Android em Flutter para consultar dados reais do backend Valcomp:

- login e cadastro por e-mail/senha;
- vinculo Riot pelo Valcomp Companion;
- loja diaria e Mercado Noturno;
- rank, RR e historico disponivel;
- wishlist de skins e alertas push via Firebase Cloud Messaging.

## Desenvolvimento

```powershell
flutter pub get
flutter analyze
flutter test
flutter run
```

O backend padrao e `https://valcomp-api-cda2.fly.dev`. Para outro ambiente:

```powershell
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## Push Android

O app so inicializa o Firebase quando todos os valores forem fornecidos:

```powershell
flutter build apk --release `
  --dart-define=FIREBASE_API_KEY=... `
  --dart-define=FIREBASE_APP_ID=... `
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... `
  --dart-define=FIREBASE_PROJECT_ID=...
```

Sem esses valores, o restante do app funciona normalmente, mas o dispositivo
nao registra um token FCM.

## Build de release

A chave local fica fora do Git:

- keystore: `E:\DevSecrets\valcomp-upload.jks`
- recuperacao: `E:\DevSecrets\valcomp-upload-key.txt`
- configuracao ignorada: `android/key.properties`

```powershell
$env:GRADLE_USER_HOME = "E:\DevCaches\gradle"
flutter build apk --release
```
