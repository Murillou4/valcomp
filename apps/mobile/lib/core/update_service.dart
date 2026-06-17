import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';

const defaultDownloadManifestUrl =
    'https://murillou4.github.io/valcomp/downloads/manifest.json';

class UpdateInfo {
  const UpdateInfo({
    required this.platform,
    required this.currentVersion,
    required this.latestVersion,
    required this.downloadUrl,
    this.currentBuild,
    this.latestBuild,
  });

  final String platform;
  final String currentVersion;
  final int? currentBuild;
  final String latestVersion;
  final int? latestBuild;
  final String downloadUrl;

  String get currentLabel =>
      currentBuild == null ? currentVersion : '$currentVersion+$currentBuild';
  String get latestLabel =>
      latestBuild == null ? latestVersion : '$latestVersion+$latestBuild';
}

class UpdateService {
  UpdateService({
    http.Client? client,
    String manifestUrl = const String.fromEnvironment(
      'DOWNLOAD_MANIFEST_URL',
      defaultValue: defaultDownloadManifestUrl,
    ),
  }) : _client = client ?? http.Client(),
       manifestUrl = manifestUrl.trim();

  final http.Client _client;
  final String manifestUrl;

  Future<UpdateInfo?> checkMobileUpdate() async {
    if (manifestUrl.isEmpty) return null;
    final installed = await PackageInfo.fromPlatform();
    final response = await _client
        .get(Uri.parse(manifestUrl), headers: {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 5));
    if (response.statusCode < 200 || response.statusCode >= 300) return null;
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) return null;
    final mobile = decoded['mobile'];
    if (mobile is! Map) return null;
    final latestVersion = mobile['version']?.toString() ?? '';
    final latestBuild = _asInt(mobile['build']);
    final currentBuild = int.tryParse(installed.buildNumber);
    if (!_isNewerVersion(
      latestVersion,
      latestBuild,
      installed.version,
      currentBuild,
    )) {
      return null;
    }
    return UpdateInfo(
      platform: 'mobile',
      currentVersion: installed.version,
      currentBuild: currentBuild,
      latestVersion: latestVersion,
      latestBuild: latestBuild,
      downloadUrl: _downloadUrl(mobile['file']?.toString() ?? ''),
    );
  }

  String _downloadUrl(String file) {
    if (file.startsWith('http://') || file.startsWith('https://')) {
      return file;
    }
    final manifest = Uri.parse(manifestUrl);
    if (file.isEmpty) return manifest.replace(path: '/valcomp/').toString();
    return manifest.resolve(file).toString();
  }
}

bool isNewerVersionForTest(
  String latestVersion,
  int? latestBuild,
  String currentVersion,
  int? currentBuild,
) {
  return _isNewerVersion(
    latestVersion,
    latestBuild,
    currentVersion,
    currentBuild,
  );
}

bool _isNewerVersion(
  String latestVersion,
  int? latestBuild,
  String currentVersion,
  int? currentBuild,
) {
  final latestParts = _versionParts(latestVersion);
  final currentParts = _versionParts(currentVersion);
  final length = latestParts.length > currentParts.length
      ? latestParts.length
      : currentParts.length;
  for (var index = 0; index < length; index++) {
    final latest = index < latestParts.length ? latestParts[index] : 0;
    final current = index < currentParts.length ? currentParts[index] : 0;
    if (latest != current) return latest > current;
  }
  if (latestBuild != null && currentBuild != null) {
    return latestBuild > currentBuild;
  }
  return false;
}

List<int> _versionParts(String version) {
  return version
      .split(RegExp(r'[.+-]'))
      .map((part) => int.tryParse(part) ?? 0)
      .toList(growable: false);
}

int? _asInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}
