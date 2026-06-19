import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_client.dart';

class RiotMobileSession {
  const RiotMobileSession({
    required this.entitlementToken,
    required this.puuid,
    required this.region,
    required this.shard,
    required this.gameName,
    required this.tagLine,
  });

  final String entitlementToken;
  final String puuid;
  final String region;
  final String shard;
  final String gameName;
  final String tagLine;
}

Future<RiotMobileSession> fetchRiotMobileSession({
  required String accessToken,
  required String idToken,
  http.Client? client,
}) async {
  final httpClient = client ?? http.Client();
  final ownsClient = client == null;
  final authHeaders = {
    'Accept': 'application/json',
    'Authorization': 'Bearer $accessToken',
    'User-Agent': '',
  };
  final jsonHeaders = {...authHeaders, 'Content-Type': 'application/json'};
  try {
    final entitlement = await _riotJson(
      httpClient.post(
        Uri.https('entitlements.auth.riotgames.com', '/api/token/v1'),
        headers: jsonHeaders,
        body: '{}',
      ),
      action: 'buscar entitlement',
      method: 'POST',
      path: '/api/token/v1',
    );
    final entitlementToken =
        entitlement['entitlements_token']?.toString() ?? '';
    if (entitlementToken.isEmpty) {
      throw const ApiException(
        'A Riot autenticou, mas não retornou o entitlement da sessão.',
        code: 'riot_entitlement_missing',
        path: '/api/token/v1',
      );
    }

    final userinfo = await _riotJson(
      httpClient.get(
        Uri.https('auth.riotgames.com', '/userinfo'),
        headers: authHeaders,
      ),
      action: 'buscar dados da conta',
      method: 'GET',
      path: '/userinfo',
    );
    final puuid = userinfo['sub']?.toString() ?? '';
    final account = _asStringMap(userinfo['acct']);
    final gameName = account['game_name'] ?? '';
    final tagLine = account['tag_line'] ?? '';

    final geo = idToken.isEmpty
        ? <String, dynamic>{}
        : await _riotJson(
            httpClient.put(
              Uri.https(
                'riot-geo.pas.si.riotgames.com',
                '/pas/v1/product/valorant',
              ),
              headers: jsonHeaders,
              body: jsonEncode({'id_token': idToken}),
            ),
            action: 'buscar região da conta',
            method: 'PUT',
            path: '/pas/v1/product/valorant',
          );
    final affinities = _asStringMap(geo['affinities']);
    final region = (affinities['live'] ?? '').toLowerCase();
    final shard = riotShardForRegion(region);

    if (puuid.isEmpty || region.isEmpty || shard.isEmpty) {
      throw const ApiException(
        'A Riot autenticou, mas não retornou PUUID e região do VALORANT.',
        code: 'riot_session_incomplete',
      );
    }

    return RiotMobileSession(
      entitlementToken: entitlementToken,
      puuid: puuid,
      region: region,
      shard: shard,
      gameName: gameName,
      tagLine: tagLine,
    );
  } finally {
    if (ownsClient) httpClient.close();
  }
}

String riotShardForRegion(String region) {
  return switch (region.toLowerCase()) {
    'na' || 'latam' || 'br' => 'na',
    'eu' => 'eu',
    'ap' => 'ap',
    'kr' => 'kr',
    _ => '',
  };
}

Future<Map<String, dynamic>> _riotJson(
  Future<http.Response> request, {
  required String action,
  required String method,
  required String path,
}) async {
  late final http.Response response;
  try {
    response = await request.timeout(const Duration(seconds: 20));
  } on TimeoutException {
    throw ApiException(
      'A Riot demorou para responder ao $action. Tente novamente.',
      code: 'riot_timeout',
      method: method,
      path: path,
    );
  } on Object {
    throw ApiException(
      'Não foi possível conectar na Riot ao $action.',
      code: 'riot_network_error',
      method: method,
      path: path,
    );
  }

  final payload = _jsonMap(response.body);
  if (response.statusCode == 401 || response.statusCode == 403) {
    throw ApiException(
      'A Riot recusou a sessão ao $action. Faça login Riot novamente pelo celular.',
      code: 'riot_auth_rejected',
      statusCode: response.statusCode,
      method: method,
      path: path,
    );
  }
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw ApiException(
      'A Riot retornou HTTP ${response.statusCode} ao $action.',
      code: 'riot_request_failed',
      statusCode: response.statusCode,
      method: method,
      path: path,
    );
  }
  return payload;
}

Map<String, dynamic> _jsonMap(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map) return Map<String, dynamic>.from(decoded);
  } on FormatException {
    // Handled by returning an empty map below.
  }
  return <String, dynamic>{};
}

Map<String, String> _asStringMap(dynamic value) {
  if (value is! Map) return const {};
  return {
    for (final entry in value.entries)
      if (entry.key != null && entry.value != null)
        entry.key.toString(): entry.value.toString(),
  };
}
