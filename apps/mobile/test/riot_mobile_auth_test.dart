import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:valcomp/core/api_client.dart';
import 'package:valcomp/core/riot_mobile_auth.dart';

void main() {
  test(
    'mobile resolves Riot session on the phone before backend upload',
    () async {
      final seen = <String>[];
      final client = MockClient((request) async {
        seen.add('${request.method} ${request.url.host}${request.url.path}');
        expect(request.headers['authorization'], 'Bearer mobile-access-token');

        if (request.url.host == 'entitlements.auth.riotgames.com') {
          expect(request.method, 'POST');
          expect(request.body, '{}');
          return http.Response(
            jsonEncode({'entitlements_token': 'mobile-entitlement'}),
            200,
          );
        }
        if (request.url.path == '/userinfo') {
          return http.Response(
            jsonEncode({
              'sub': 'mobile-puuid',
              'acct': {'game_name': 'Mobile', 'tag_line': 'BR1'},
            }),
            200,
          );
        }
        if (request.url.host == 'riot-geo.pas.si.riotgames.com') {
          expect(request.method, 'PUT');
          expect(jsonDecode(request.body), {'id_token': 'mobile-id-token'});
          return http.Response(
            jsonEncode({
              'affinities': {'live': 'br'},
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      });

      final session = await fetchRiotMobileSession(
        accessToken: 'mobile-access-token',
        idToken: 'mobile-id-token',
        client: client,
      );

      expect(session.entitlementToken, 'mobile-entitlement');
      expect(session.puuid, 'mobile-puuid');
      expect(session.region, 'br');
      expect(session.shard, 'na');
      expect(session.gameName, 'Mobile');
      expect(session.tagLine, 'BR1');
      expect(seen, [
        'POST entitlements.auth.riotgames.com/api/token/v1',
        'GET auth.riotgames.com/userinfo',
        'PUT riot-geo.pas.si.riotgames.com/pas/v1/product/valorant',
      ]);
    },
  );

  test(
    'mobile reports entitlement rejection before contacting backend',
    () async {
      final client = MockClient(
        (_) async => http.Response(jsonEncode({'error': 'forbidden'}), 403),
      );

      expect(
        () => fetchRiotMobileSession(
          accessToken: 'mobile-access-token',
          idToken: 'mobile-id-token',
          client: client,
        ),
        throwsA(
          isA<ApiException>()
              .having((error) => error.code, 'code', 'riot_auth_rejected')
              .having((error) => error.statusCode, 'statusCode', 403)
              .having((error) => error.path, 'path', '/api/token/v1'),
        ),
      );
    },
  );
}
