import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:valcomp/core/theme.dart';
import 'package:valcomp/core/update_service.dart';
import 'package:valcomp/screens/riot_mobile_login_screen.dart';

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
}
