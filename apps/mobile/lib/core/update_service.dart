import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';

const defaultDownloadManifestUrl =
    'https://murillou4.github.io/valcomp/downloads/manifest.json';
const defaultFallbackManifestUrl =
    'https://raw.githubusercontent.com/Murillou4/valcomp/main/docs/downloads/manifest.json';

typedef PackageInfoLoader = Future<PackageInfo> Function();

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
    PackageInfoLoader? packageInfoLoader,
    List<String>? fallbackManifestUrls,
    String manifestUrl = const String.fromEnvironment(
      'DOWNLOAD_MANIFEST_URL',
      defaultValue: defaultDownloadManifestUrl,
    ),
  }) : _client = client ?? http.Client(),
       _packageInfoLoader = packageInfoLoader ?? PackageInfo.fromPlatform,
       fallbackManifestUrls =
           fallbackManifestUrls ?? const [defaultFallbackManifestUrl],
       manifestUrl = manifestUrl.trim();

  final http.Client _client;
  final PackageInfoLoader _packageInfoLoader;
  final String manifestUrl;
  final List<String> fallbackManifestUrls;

  Future<UpdateInfo?> checkMobileUpdate() async {
    if (manifestUrl.isEmpty) return null;
    final installed = await _packageInfoLoader();
    final manifest = await _fetchManifest();
    if (manifest == null) return null;
    final (decoded, sourceUri) = manifest;
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
      downloadUrl: _downloadUrl(mobile['file']?.toString() ?? '', sourceUri),
    );
  }

  Future<(Map<dynamic, dynamic>, Uri)?> _fetchManifest() async {
    final candidates = <String>{manifestUrl, ...fallbackManifestUrls};
    Object? lastError;
    for (final candidate in candidates) {
      if (candidate.trim().isEmpty) continue;
      final original = Uri.parse(candidate.trim());
      final uri = original.replace(
        queryParameters: {
          ...original.queryParameters,
          '_valcomp_update': DateTime.now().millisecondsSinceEpoch.toString(),
        },
      );
      try {
        final response = await _client
            .get(
              uri,
              headers: const {
                'Accept': 'application/json',
                'Cache-Control': 'no-cache, no-store, max-age=0',
                'Pragma': 'no-cache',
              },
            )
            .timeout(const Duration(seconds: 8));
        if (response.statusCode < 200 || response.statusCode >= 300) {
          lastError = 'HTTP ${response.statusCode}';
          continue;
        }
        final decoded = jsonDecode(response.body);
        if (decoded is Map && decoded['mobile'] is Map) {
          return (decoded, original);
        }
        lastError = const FormatException('Manifesto de atualização inválido.');
      } on Object catch (error) {
        lastError = error;
      }
    }
    if (lastError != null) throw lastError;
    return null;
  }

  String _downloadUrl(String file, Uri sourceManifest) {
    if (file.startsWith('http://') || file.startsWith('https://')) {
      return file;
    }
    if (file.isEmpty) {
      return Uri.parse(manifestUrl).resolve('/valcomp/').toString();
    }
    return sourceManifest.resolve(file).toString();
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
