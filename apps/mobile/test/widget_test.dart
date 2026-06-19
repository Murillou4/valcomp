import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import 'package:valcomp/core/api_client.dart';
import 'package:valcomp/core/app_controller.dart';
import 'package:valcomp/core/models.dart';
import 'package:valcomp/core/push_service.dart';
import 'package:valcomp/core/theme.dart';
import 'package:valcomp/core/update_service.dart';
import 'package:valcomp/screens/riot_mobile_login_screen.dart';
import 'package:valcomp/screens/app_shell.dart';

void main() {
  testWidgets('Valcomp theme uses the expected dark background', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildValcompTheme(),
        home: const Scaffold(body: Text('Valcomp')),
      ),
    );

    expect(find.text('Valcomp'), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, isNull);
    expect(
      Theme.of(tester.element(find.text('Valcomp'))).scaffoldBackgroundColor,
      ValcompColors.background,
    );
  });

  test('Riot mobile login parser extracts redirect tokens', () {
    final tokens = riotTokenParametersFromUrlForTest(
      'http://localhost/redirect#access_token=access-123&id_token=id-456&token_type=bearer',
    );

    expect(tokens, isNotNull);
    expect(tokens!['access_token'], 'access-123');
    expect(tokens['id_token'], 'id-456');
  });

  test('Riot mobile login uses Riot client authorization', () {
    final loginUri = Uri.parse(riotLoginUrlForTest());

    expect(loginUri.host, 'auth.riotgames.com');
    expect(loginUri.path, '/authorize');
    expect(loginUri.queryParameters['client_id'], 'riot-client');
    expect(
      loginUri.queryParameters['redirect_uri'],
      'http://localhost/redirect',
    );
    expect(
      loginUri.queryParameters['scope'],
      'openid link ban lol_region account',
    );
  });

  test('Riot mobile login maps Valorant regions to shards', () {
    expect(riotShardForRegionForTest('br'), 'na');
    expect(riotShardForRegionForTest('latam'), 'na');
    expect(riotShardForRegionForTest('eu'), 'eu');
  });

  test('update version comparator honors version and build', () {
    expect(isNewerVersionForTest('1.1.6', 1, '1.1.5', 99), isTrue);
    expect(isNewerVersionForTest('1.1.5', 10, '1.1.5', 9), isTrue);
    expect(isNewerVersionForTest('1.1.5', 9, '1.1.5', 9), isFalse);
    expect(isNewerVersionForTest('1.1.4', 99, '1.1.5', 1), isFalse);
  });

  test(
    'update check bypasses cache and falls back to a second manifest',
    () async {
      final requests = <http.Request>[];
      final client = MockClient((request) async {
        requests.add(request);
        if (request.url.host == 'pages.example.test') {
          return http.Response('temporarily unavailable', 503);
        }
        return http.Response(
          '{"mobile":{"version":"1.3.2","build":17,"file":"valcomp-mobile.apk"}}',
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final service = UpdateService(
        client: client,
        manifestUrl: 'https://pages.example.test/downloads/manifest.json',
        fallbackManifestUrls: const [
          'https://raw.example.test/main/docs/downloads/manifest.json',
        ],
        packageInfoLoader: () async => PackageInfo(
          appName: 'Valcomp',
          packageName: 'com.cda2.valcomp',
          version: '1.2.0',
          buildNumber: '14',
        ),
      );

      final info = await service.checkMobileUpdate();

      expect(info?.latestLabel, '1.3.2+17');
      expect(
        info?.downloadUrl,
        'https://raw.example.test/main/docs/downloads/valcomp-mobile.apk',
      );
      expect(requests, hasLength(2));
      expect(
        requests.every(
          (request) =>
              request.url.queryParameters.containsKey('_valcomp_update') &&
              request.headers['Cache-Control']?.contains('no-cache') == true,
        ),
        isTrue,
      );
    },
  );

  testWidgets('available update opens a global prompt inside the app', (
    tester,
  ) async {
    final controller = AppController(pushService: PushService())
      ..authenticated = true
      ..me = const MeData(
        profile: Profile(
          userId: 'user-1',
          displayName: 'Player',
          avatarUrl: '',
        ),
        riotAccount: RiotAccount(
          gameName: 'Player',
          tagLine: 'BR1',
          region: 'br',
          shard: 'na',
        ),
      )
      ..updateInfo = const UpdateInfo(
        platform: 'mobile',
        currentVersion: '1.2.0',
        currentBuild: 14,
        latestVersion: '1.3.2',
        latestBuild: 17,
        downloadUrl: 'https://example.test/valcomp-mobile.apk',
      );
    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: controller,
        child: MaterialApp(theme: buildValcompTheme(), home: const AppShell()),
      ),
    );
    await tester.pump();

    expect(find.text('Nova versão disponível'), findsOneWidget);
    expect(
      find.text('A versão 1.3.2+17 do Valcomp já pode ser instalada.'),
      findsOneWidget,
    );
    expect(find.text('Baixar agora'), findsOneWidget);
    controller.dispose();
  });

  test('Riot setup is required for first link and invalidated sessions', () {
    final controller = AppController(pushService: PushService())
      ..authenticated = true
      ..me = const MeData(
        profile: Profile(
          userId: 'user-1',
          displayName: 'Player',
          avatarUrl: '',
        ),
      );

    expect(controller.requiresRiotSetup, isTrue);

    controller.me = MeData(
      profile: controller.me!.profile,
      riotAccount: const RiotAccount(
        gameName: 'Player',
        tagLine: 'BR1',
        region: 'br',
        shard: 'na',
      ),
    );
    expect(controller.requiresRiotSetup, isFalse);

    controller.handleRiotRelinkNotification();
    expect(controller.relinkRequired, isTrue);
    expect(controller.requiresRiotSetup, isTrue);
    controller.dispose();
  });

  test('API relink response immediately invalidates Riot state', () async {
    final api = ApiClient(
      baseUrl: 'https://example.test',
      client: MockClient(
        (_) async => http.Response(
          '{"error":{"code":"relink_required","message":"expired"}}',
          409,
          headers: {'content-type': 'application/json'},
        ),
      ),
    );
    var invalidated = false;
    api.onRiotRelinkRequired = () => invalidated = true;

    await expectLater(
      api.request('GET', '/riot/session/status', authenticated: false),
      throwsA(isA<ApiException>()),
    );
    expect(invalidated, isTrue);
  });
}
