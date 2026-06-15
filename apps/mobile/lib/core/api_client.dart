import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, {this.code = '', this.statusCode = 0});

  final String message;
  final String code;
  final int statusCode;

  bool get relinkRequired => code == 'relink_required';

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    http.Client? client,
    FlutterSecureStorage? storage,
    String? baseUrl,
  }) : _client = client ?? http.Client(),
       _storage = storage ?? const FlutterSecureStorage(),
       baseUrl =
           (baseUrl ??
                   const String.fromEnvironment(
                     'API_BASE_URL',
                     defaultValue: 'https://valcomp-api-cda2.fly.dev',
                   ))
               .replaceAll(RegExp(r'/$'), '');

  final http.Client _client;
  final FlutterSecureStorage _storage;
  final String baseUrl;

  String _accessToken = '';
  String _refreshToken = '';

  bool get hasSession => _accessToken.isNotEmpty;

  Future<void> restoreSession() async {
    _accessToken = await _storage.read(key: 'access_token') ?? '';
    _refreshToken = await _storage.read(key: 'refresh_token') ?? '';
  }

  Future<void> saveSession(Map<String, dynamic> response) async {
    final session = _asMap(response['session']);
    _accessToken = session['access_token']?.toString() ?? '';
    _refreshToken = session['refresh_token']?.toString() ?? _refreshToken;
    if (_accessToken.isNotEmpty) {
      await _storage.write(key: 'access_token', value: _accessToken);
    }
    if (_refreshToken.isNotEmpty) {
      await _storage.write(key: 'refresh_token', value: _refreshToken);
    }
  }

  Future<void> clearSession() async {
    _accessToken = '';
    _refreshToken = '';
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final result = await request(
      'POST',
      '/auth/login',
      authenticated: false,
      body: {'email': email, 'password': password, 'display_name': ''},
    );
    await saveSession(result);
    return result;
  }

  Future<Map<String, dynamic>> signup(
    String name,
    String email,
    String password,
  ) async {
    final result = await request(
      'POST',
      '/auth/signup',
      authenticated: false,
      body: {'email': email, 'password': password, 'display_name': name},
    );
    if (result['session'] is Map) await saveSession(result);
    return result;
  }

  Future<bool> refreshSession() async {
    if (_refreshToken.isEmpty) return false;
    try {
      final result = await request(
        'POST',
        '/auth/refresh',
        authenticated: false,
        body: {'refresh_token': _refreshToken},
      );
      await saveSession(result);
      return hasSession;
    } on ApiException {
      return false;
    }
  }

  Future<Map<String, dynamic>> get(String path) => request('GET', path);

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
  }) => request('POST', path, body: body);

  Future<Map<String, dynamic>> patch(
    String path, {
    Map<String, dynamic>? body,
  }) => request('PATCH', path, body: body);

  Future<Map<String, dynamic>> delete(String path) => request('DELETE', path);

  Future<Map<String, dynamic>> request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
    bool retry = true,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null) headers['Content-Type'] = 'application/json';
    if (authenticated && _accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    final encoded = body == null ? null : jsonEncode(body);
    final response = switch (method) {
      'POST' => await _client.post(uri, headers: headers, body: encoded),
      'PATCH' => await _client.patch(uri, headers: headers, body: encoded),
      'DELETE' => await _client.delete(uri, headers: headers),
      _ => await _client.get(uri, headers: headers),
    };
    if (response.statusCode == 401 &&
        authenticated &&
        retry &&
        await refreshSession()) {
      return request(
        method,
        path,
        body: body,
        authenticated: true,
        retry: false,
      );
    }
    dynamic decoded;
    try {
      decoded = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body);
    } on FormatException {
      decoded = <String, dynamic>{};
    }
    final payload = _asMap(decoded);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = payload['error'] ?? payload['detail'];
      final error = _asMap(detail);
      throw ApiException(
        error['message']?.toString() ??
            payload['message']?.toString() ??
            'Não foi possível concluir esta ação.',
        code: error['code']?.toString() ?? '',
        statusCode: response.statusCode,
      );
    }
    return payload;
  }
}

Map<String, dynamic> _asMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
