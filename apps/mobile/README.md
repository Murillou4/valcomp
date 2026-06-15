# Valcomp Mobile

Aplicativo Android em Flutter para consultar dados reais do backend Valcomp:

- login e cadastro por e-mail/senha;
- vinculo Riot pelo Valcomp Companion;
- loja diaria e Mercado Noturno;
- rank, RR, historico e detalhes completos das partidas;
- detalhes de skins com inventario, loja e Mercado Noturno;
- wishlist de skins e alertas push via Firebase Cloud Messaging.
- diagnosticos locais e remotos sanitizados, copiaveis pela tela Conta.

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

O app Android esta registrado no projeto Firebase `valorant-dc041`. A
configuracao publica gerada pelo FlutterFire fica em:

- `android/app/google-services.json`
- `lib/firebase_options.dart`

Nao sao necessarios `--dart-define` para o Firebase. Depois do login, o app
solicita permissao do Android, registra o token FCM no backend e acompanha
automaticamente futuras trocas desse token.

A tela `Alertas` permite enviar uma notificacao de teste para os aparelhos
registrados do proprio usuario.

A chave privada da Service Account pertence somente ao backend e fica fora do
Git.

## Build de release

A chave local fica fora do Git:

- keystore: `E:\DevSecrets\valcomp-upload.jks`
- recuperacao: `E:\DevSecrets\valcomp-upload-key.txt`
- configuracao ignorada: `android/key.properties`

```powershell
$env:GRADLE_USER_HOME = "E:\DevCaches\gradle"
flutter build apk --release
```
