import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';

class DiagnosticLog {
  DiagnosticLog._();

  static final instance = DiagnosticLog._();

  static const _maxFileBytes = 2 * 1024 * 1024;
  static const _maxExportLines = 300;

  File? _file;
  Future<void> _writeChain = Future.value();
  String appVersion = 'unknown';

  Future<void> initialize() async {
    final package = await PackageInfo.fromPlatform();
    appVersion = '${package.version}+${package.buildNumber}';
    final directory = await getApplicationSupportDirectory();
    await directory.create(recursive: true);
    _file = File(
      '${directory.path}${Platform.pathSeparator}valcomp-diagnostics.jsonl',
    );
    await _rotateIfNeeded();
    await record(
      level: 'info',
      category: 'lifecycle',
      message: 'Aplicativo iniciado.',
      context: {
        'app_version': appVersion,
        'platform': Platform.operatingSystem,
      },
    );
  }

  Future<void> record({
    required String level,
    required String category,
    required String message,
    Map<String, Object?> context = const {},
    String stackTrace = '',
    String requestId = '',
  }) {
    final event = <String, Object?>{
      'event_id': newEventId(),
      'source': 'mobile',
      'level': level,
      'category': category,
      'message': _redactText(message),
      'context': _sanitize(context),
      'stack_trace': _redactText(stackTrace, maxLength: 16000),
      'request_id': requestId,
      'app_version': appVersion,
      'occurred_at': DateTime.now().toUtc().toIso8601String(),
    };
    _writeChain = _writeChain
        .then((_) async {
          final file = _file;
          if (file == null) return;
          await _rotateIfNeeded();
          await file.writeAsString(
            '${jsonEncode(event)}\n',
            mode: FileMode.append,
            flush: true,
          );
        })
        .catchError((_) {
          // Diagnostics must never crash the app they are observing.
        });
    return _writeChain;
  }

  Future<String> exportText() async {
    await _writeChain;
    final file = _file;
    if (file == null || !await file.exists()) {
      return 'Nenhum diagnóstico local disponível.';
    }
    final lines = await file.readAsLines();
    final selected = lines.length <= _maxExportLines
        ? lines
        : lines.sublist(lines.length - _maxExportLines);
    return [
      'VALCOMP DIAGNOSTICS',
      'App: $appVersion',
      'Plataforma: ${Platform.operatingSystem} ${Platform.operatingSystemVersion}',
      'Arquivo local: ${file.path}',
      'Eventos: ${selected.length}',
      '',
      ...selected,
    ].join('\n');
  }

  String newEventId() =>
      'mob-${DateTime.now().microsecondsSinceEpoch}-${identityHashCode(Object())}';

  Future<void> _rotateIfNeeded() async {
    final file = _file;
    if (file == null || !await file.exists()) return;
    if (await file.length() <= _maxFileBytes) return;
    final backup = File('${file.path}.1');
    if (await backup.exists()) await backup.delete();
    await file.rename(backup.path);
    _file = File(file.path);
  }
}

Object? _sanitize(Object? value, {int depth = 0}) {
  if (depth > 5) return '[MAX_DEPTH]';
  if (value is Map) {
    final result = <String, Object?>{};
    for (final entry in value.entries.take(80)) {
      final key = entry.key.toString();
      final lower = key.toLowerCase();
      if (_secretKeys.any(lower.contains)) {
        result[key] = '[REDACTED]';
      } else {
        result[key] = _sanitize(entry.value, depth: depth + 1);
      }
    }
    return result;
  }
  if (value is Iterable) {
    return value
        .take(80)
        .map((item) => _sanitize(item, depth: depth + 1))
        .toList();
  }
  if (value is String) return _redactText(value);
  if (value == null || value is num || value is bool) return value;
  return _redactText(value.toString());
}

String _redactText(String value, {int maxLength = 8000}) {
  var text = value.length <= maxLength ? value : value.substring(0, maxLength);
  text = text.replaceAll(
    RegExp(
      r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?\b',
    ),
    '[REDACTED_JWT]',
  );
  text = text.replaceAll(
    RegExp(r'\bBearer\s+[A-Za-z0-9._~+/=-]{12,}', caseSensitive: false),
    'Bearer [REDACTED]',
  );
  text = text.replaceAll(
    RegExp(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', caseSensitive: false),
    '[REDACTED_EMAIL]',
  );
  text = text.replaceAll(
    RegExp(
      r'\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b',
      caseSensitive: false,
    ),
    '[REDACTED_ID]',
  );
  return text;
}

const _secretKeys = {
  'access_token',
  'authorization',
  'cookie',
  'cookies',
  'entitlement',
  'password',
  'puuid',
  'refresh_token',
  'secret',
  'ssid',
  'token',
};
