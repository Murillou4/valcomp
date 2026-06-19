import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'api_client.dart';
import 'diagnostic_log.dart';
import 'live_models.dart';

class LiveService {
  LiveService(
    this.api, {
    required this.onSnapshot,
    required this.onCommand,
    required this.onConnection,
    required this.onRiotSession,
  });

  final ApiClient api;
  final void Function(LiveSnapshot snapshot) onSnapshot;
  final void Function(LiveCommandResult command) onCommand;
  final void Function(bool connected, String message) onConnection;
  final void Function() onRiotSession;

  WebSocket? _socket;
  Timer? _reconnectTimer;
  Timer? _pollTimer;
  Timer? _pingTimer;
  bool _closed = true;
  bool _connecting = false;
  int _attempt = 0;

  Future<void> start() async {
    if (!api.hasSession) return;
    _closed = false;
    await refreshState();
    await connect();
    _pollTimer ??= Timer.periodic(const Duration(seconds: 12), (_) {
      unawaited(refreshState());
    });
  }

  Future<void> connect() async {
    if (_closed || !api.hasSession || _socket != null || _connecting) return;
    _connecting = true;
    final uri = Uri.parse(api.baseUrl).replace(
      scheme: api.baseUrl.startsWith('https') ? 'wss' : 'ws',
      path: '/ws/live',
    );
    try {
      final socket = await WebSocket.connect(
        uri.toString(),
        headers: {'Authorization': 'Bearer ${api.accessToken}'},
      ).timeout(const Duration(seconds: 12));
      _socket = socket;
      _attempt = 0;
      onConnection(true, 'Companion conectado');
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(const Duration(seconds: 15), (_) {
        socket.add(jsonEncode({'type': 'ping'}));
      });
      socket.listen(
        _handleMessage,
        onDone: () => _disconnected('Companion desconectado'),
        onError: (Object error, StackTrace stack) {
          unawaited(
            DiagnosticLog.instance.record(
              level: 'warning',
              category: 'live_websocket',
              message: error.toString(),
              stackTrace: stack.toString(),
            ),
          );
          _disconnected('Reconectando ao Companion');
        },
        cancelOnError: true,
      );
    } on Object catch (error) {
      onConnection(false, 'Companion offline');
      await DiagnosticLog.instance.record(
        level: 'debug',
        category: 'live_connect',
        message: error.toString(),
      );
      _scheduleReconnect();
    } finally {
      _connecting = false;
    }
  }

  void _handleMessage(dynamic raw) {
    try {
      final decoded = jsonDecode(raw.toString());
      final message = liveMap(decoded);
      if (message['type'] == 'snapshot') {
        onSnapshot(LiveSnapshot.fromJson(message));
      } else if (message['type'] == 'command_result') {
        onCommand(LiveCommandResult.fromJson(liveMap(message['command'])));
      } else if (message['type'] == 'riot_session' && message['valid'] == true) {
        onRiotSession();
      }
    } on Object catch (error) {
      unawaited(
        DiagnosticLog.instance.record(
          level: 'warning',
          category: 'live_message',
          message: error.toString(),
        ),
      );
    }
  }

  Future<void> refreshState() async {
    if (!api.hasSession) return;
    try {
      onSnapshot(LiveSnapshot.fromJson(await api.get('/live/state')));
    } on ApiException catch (error) {
      onConnection(false, error.message);
    }
  }

  Future<CompanionPairCode> startPairing() async =>
      CompanionPairCode.fromJson(await api.post('/companion/pair/start'));

  Future<List<CompanionDevice>> devices() async {
    final response = await api.get('/companion/devices');
    return (response['devices'] as List? ?? const [])
        .whereType<Map>()
        .map(
          (item) => CompanionDevice.fromJson(Map<String, dynamic>.from(item)),
        )
        .toList();
  }

  Future<void> revokeDevice(String deviceId) async {
    await api.delete('/companion/devices/$deviceId');
  }

  Future<LiveCommandResult> command(
    String command,
    Map<String, dynamic> payload,
  ) async {
    final commandId = 'mob-${DateTime.now().microsecondsSinceEpoch}';
    final response = await api.post(
      '/live/commands',
      body: {'command_id': commandId, 'command': command, 'payload': payload},
    );
    return LiveCommandResult.fromJson(liveMap(response['command']));
  }

  void _disconnected(String message) {
    _socket = null;
    _pingTimer?.cancel();
    _pingTimer = null;
    if (_closed) return;
    onConnection(false, message);
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_closed || _reconnectTimer != null) return;
    final seconds = [1, 2, 4, 8, 16, 30][_attempt.clamp(0, 5)];
    _attempt++;
    _reconnectTimer = Timer(Duration(seconds: seconds), () {
      _reconnectTimer = null;
      unawaited(connect());
    });
  }

  Future<void> stop() async {
    _closed = true;
    _reconnectTimer?.cancel();
    _pollTimer?.cancel();
    _pingTimer?.cancel();
    _reconnectTimer = null;
    _pollTimer = null;
    _pingTimer = null;
    final socket = _socket;
    _socket = null;
    await socket?.close();
  }
}
