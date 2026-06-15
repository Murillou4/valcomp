import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'diagnostic_log.dart';

class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.code = '',
    this.statusCode = 0,
    this.requestId = '',
    this.method = '',
    this.path = '',
  });

  final String message;
  final String code;
  final int statusCode;
  final String requestId;
  final String method;
  final String path;

  bool get relinkRequired => code == 'relink_required';
  String get userMessage =>
      requestId.isEmpty ? message : '$message\nReferência: $requestId';
  String get fullDetails => const JsonEncoder.withIndent('  ').convert({
    'message': message,
    'code': code,
    'status_code': statusCode,
    'request_id': requestId,
    'method': method,
    'path': path,
  });

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
    final requestId = DiagnosticLog.instance.newEventId();
    final stopwatch = Stopwatch()..start();
    final headers = <String, String>{
      'Accept': 'application/json',
      'X-Request-ID': requestId,
      'X-Valcomp-Client': 'mobile/${DiagnosticLog.instance.appVersion}',
    };
    if (body != null) headers['Content-Type'] = 'application/json';
    if (authenticated && _accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    final encoded = body == null ? null : jsonEncode(body);
    unawaited(
      DiagnosticLog.instance.record(
        level: 'debug',
        category: 'api_request',
        message: '$method $path',
        requestId: requestId,
      ),
    );
    late final http.Response response;
    try {
      response = switch (method) {
        'POST' => await _client.post(uri, headers: headers, body: encoded),
        'PATCH' => await _client.patch(uri, headers: headers, body: encoded),
        'DELETE' => await _client.delete(uri, headers: headers),
        _ => await _client.get(uri, headers: headers),
      };
    } on Object catch (error, stack) {
      stopwatch.stop();
      final exception = ApiException(
        error is SocketException || error is TimeoutException
            ? 'Não foi possível conectar ao Valcomp. Verifique sua internet e tente novamente.'
            : 'A conexão falhou antes de receber uma resposta.',
        code: 'network_error',
        requestId: requestId,
        method: method,
        path: path,
      );
      unawaited(
        DiagnosticLog.instance.record(
          level: 'error',
          category: 'api_network_error',
          message: error.toString(),
          stackTrace: stack.toString(),
          requestId: requestId,
          context: {
            'method': method,
            'path': path,
            'elapsed_ms': stopwatch.elapsedMilliseconds,
          },
        ),
      );
      throw exception;
    }
    stopwatch.stop();
    unawaited(
      DiagnosticLog.instance.record(
        level: response.statusCode >= 400 ? 'warning' : 'debug',
        category: 'api_response',
        message: '$method $path -> ${response.statusCode}',
        requestId: requestId,
        context: {
          'status_code': response.statusCode,
          'elapsed_ms': stopwatch.elapsedMilliseconds,
        },
      ),
    );
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
      final exception = ApiException(
        error['message']?.toString() ??
            payload['message']?.toString() ??
            'Não foi possível concluir esta ação.',
        code: error['code']?.toString() ?? '',
        statusCode: response.statusCode,
        requestId:
            error['request_id']?.toString() ??
            response.headers['x-request-id'] ??
            requestId,
        method: method,
        path: path,
      );
      unawaited(_uploadDiagnostic(exception));
      throw exception;
    }
    return payload;
  }

  Future<void> _uploadDiagnostic(ApiException exception) async {
    if (_accessToken.isEmpty || exception.path.startsWith('/diagnostics/')) {
      return;
    }
    try {
      await _client
          .post(
            Uri.parse('$baseUrl/diagnostics/events'),
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $_accessToken',
              'X-Request-ID': exception.requestId,
              'X-Valcomp-Client': 'mobile/${DiagnosticLog.instance.appVersion}',
            },
            body: jsonEncode({
              'event_id': DiagnosticLog.instance.newEventId(),
              'source': 'mobile',
              'level': exception.statusCode >= 500 ? 'error' : 'warning',
              'category': exception.code.isEmpty ? 'api_error' : exception.code,
              'message': exception.message,
              'context': {
                'method': exception.method,
                'path': exception.path,
                'status_code': exception.statusCode,
              },
              'request_id': exception.requestId,
              'app_version': DiagnosticLog.instance.appVersion,
            }),
          )
          .timeout(const Duration(seconds: 5));
    } on Object catch (error) {
      await DiagnosticLog.instance.record(
        level: 'warning',
        category: 'diagnostic_upload_failed',
        message: error.toString(),
        requestId: exception.requestId,
      );
    }
  }
}

Map<String, dynamic> _asMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
