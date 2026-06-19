class LiveSnapshot {
  const LiveSnapshot({
    required this.phase,
    required this.revision,
    required this.state,
    required this.online,
    this.updatedAt,
  });

  final String phase;
  final int revision;
  final Map<String, dynamic> state;
  final bool online;
  final DateTime? updatedAt;

  factory LiveSnapshot.offline([String reason = 'companion_not_connected']) =>
      LiveSnapshot(
        phase: 'offline',
        revision: 0,
        state: {'reason': reason},
        online: false,
      );

  factory LiveSnapshot.fromJson(Map<String, dynamic> json) => LiveSnapshot(
    phase: json['phase']?.toString() ?? 'offline',
    revision: (json['revision'] as num?)?.toInt() ?? 0,
    state: liveMap(json['state']),
    online: json['online'] == true,
    updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? ''),
  );

  Map<String, dynamic> get party => liveMap(state['party']);
  Map<String, dynamic> get queue => liveMap(state['queue']);
  Map<String, dynamic> get match => liveMap(state['match']);
  Map<String, dynamic> get map => liveMap(match['map'] ?? state['map']);
  Map<String, dynamic> get capabilities => liveMap(state['capabilities']);
  List<Map<String, dynamic>> get members => liveMaps(party['members']);
  List<Map<String, dynamic>> get agents => liveMaps(state['agents']);
  List<Map<String, dynamic>> get availableAgents =>
      liveMaps(state['available_agents']);
  List<Map<String, dynamic>> get team => liveMaps(match['team']);
  List<Map<String, dynamic>> get chatChannels =>
      liveMaps(state['chat_channels']);
}

class CompanionDevice {
  const CompanionDevice({
    required this.deviceId,
    required this.deviceName,
    required this.appVersion,
    required this.active,
    required this.online,
    this.lastSeenAt,
  });

  final String deviceId;
  final String deviceName;
  final String appVersion;
  final bool active;
  final bool online;
  final DateTime? lastSeenAt;

  factory CompanionDevice.fromJson(Map<String, dynamic> json) {
    final lastSeen = DateTime.tryParse(json['last_seen_at']?.toString() ?? '');
    return CompanionDevice(
      deviceId: json['device_id']?.toString() ?? '',
      deviceName: json['device_name']?.toString() ?? 'Companion',
      appVersion: json['app_version']?.toString() ?? '',
      active: json['active'] == true && json['revoked_at'] == null,
      online:
          lastSeen != null &&
          DateTime.now().toUtc().difference(lastSeen.toUtc()) <
              const Duration(seconds: 25),
      lastSeenAt: lastSeen,
    );
  }
}

class CompanionPairCode {
  const CompanionPairCode({required this.code, required this.expiresAt});

  final String code;
  final DateTime expiresAt;

  factory CompanionPairCode.fromJson(Map<String, dynamic> json) =>
      CompanionPairCode(
        code: json['pair_code']?.toString() ?? '',
        expiresAt:
            DateTime.tryParse(json['expires_at']?.toString() ?? '') ??
            DateTime.now().add(const Duration(minutes: 10)),
      );
}

class LiveCommandResult {
  const LiveCommandResult({
    required this.commandId,
    required this.command,
    required this.status,
    required this.result,
  });

  final String commandId;
  final String command;
  final String status;
  final Map<String, dynamic> result;

  bool get finished =>
      const {'succeeded', 'rejected', 'failed', 'expired'}.contains(status);

  factory LiveCommandResult.fromJson(Map<String, dynamic> json) =>
      LiveCommandResult(
        commandId: json['command_id']?.toString() ?? '',
        command: json['command']?.toString() ?? '',
        status: json['status']?.toString() ?? 'queued',
        result: liveMap(json['result']),
      );
}

Map<String, dynamic> liveMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<Map<String, dynamic>> liveMaps(dynamic value) => value is List
    ? value
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList()
    : const [];
