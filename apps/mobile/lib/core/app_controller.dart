import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'models.dart';
import 'push_service.dart';

class AppController extends ChangeNotifier {
  AppController({ApiClient? api, required PushService pushService})
    : api = api ?? ApiClient(),
      _pushService = pushService;

  final ApiClient api;
  final PushService _pushService;

  bool booting = true;
  bool authenticated = false;
  bool loading = false;
  bool relinkRequired = false;
  String error = '';
  int navIndex = 1;
  MeData? me;
  DailyStore? store;
  PlayerSummary? player;
  List<SkinWatch> watches = const [];
  List<NotificationDelivery> deliveries = const [];
  SkinCatalog? skinCatalog;
  bool skinCatalogLoading = false;
  String linkCode = '';
  DateTime? linkExpiresAt;

  bool get linked => me?.riotAccount != null && !relinkRequired;
  String get displayName {
    final value = me?.profile.displayName.trim() ?? '';
    return value.isEmpty ? 'Agente' : value.split(' ').first;
  }

  Future<void> bootstrap() async {
    await api.restoreSession();
    if (api.hasSession) {
      try {
        await api.post('/auth/session/verify');
        authenticated = true;
        await refreshAll(silent: true);
      } on ApiException {
        if (await api.refreshSession()) {
          authenticated = true;
          await refreshAll(silent: true);
        } else {
          await api.clearSession();
        }
      }
    }
    booting = false;
    notifyListeners();
  }

  Future<String?> login(String email, String password) async {
    return _runAuth(() => api.login(email.trim(), password));
  }

  Future<String?> signup(String name, String email, String password) async {
    return _runAuth(() => api.signup(name.trim(), email.trim(), password));
  }

  Future<String?> _runAuth(
    Future<Map<String, dynamic>> Function() action,
  ) async {
    loading = true;
    error = '';
    notifyListeners();
    try {
      final result = await action();
      if (result['email_confirmation_required'] == true ||
          result['session'] == null) {
        return result['message']?.toString() ??
            'Confira seu e-mail para confirmar a conta.';
      }
      authenticated = true;
      await refreshAll(silent: true);
      unawaited(_pushService.register(api));
      return null;
    } on ApiException catch (exception) {
      error = exception.message;
      return exception.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await api.clearSession();
    authenticated = false;
    me = null;
    store = null;
    player = null;
    watches = const [];
    deliveries = const [];
    notifyListeners();
  }

  Future<void> refreshAll({bool silent = false}) async {
    if (!silent) {
      loading = true;
      notifyListeners();
    }
    error = '';
    try {
      me = MeData.fromJson(await api.get('/me'));
      relinkRequired = false;
      await _loadWatchData();
      if (me?.riotAccount != null) {
        await Future.wait([loadStore(), loadPlayer()]);
      } else {
        store = null;
        player = null;
      }
      unawaited(_pushService.register(api));
    } on ApiException catch (exception) {
      if (exception.relinkRequired) {
        relinkRequired = true;
      } else {
        error = exception.message;
      }
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> _loadWatchData() async {
    final responses = await Future.wait([
      api.get('/valorant/skins/watchlist'),
      api.get('/notifications/deliveries?limit=50'),
    ]);
    watches = _list(
      responses[0]['items'],
    ).map((e) => SkinWatch.fromJson(_map(e))).toList();
    deliveries = _list(
      responses[1]['deliveries'],
    ).map((e) => NotificationDelivery.fromJson(_map(e))).toList();
  }

  Future<void> loadStore() async {
    try {
      store = DailyStore.fromJson(await api.get('/valorant/store/daily'));
      relinkRequired = false;
    } on ApiException catch (exception) {
      if (exception.relinkRequired) relinkRequired = true;
      rethrow;
    }
  }

  Future<void> loadPlayer() async {
    try {
      player = PlayerSummary.fromJson(
        await api.get('/valorant/player/summary'),
      );
    } on ApiException catch (exception) {
      if (exception.relinkRequired) relinkRequired = true;
      rethrow;
    }
  }

  void selectTab(int index) {
    if (navIndex == index) return;
    navIndex = index;
    notifyListeners();
  }

  Future<void> generateLinkCode() async {
    loading = true;
    notifyListeners();
    try {
      final response = await api.post('/riot/link/start');
      linkCode = response['link_code']?.toString() ?? '';
      linkExpiresAt = DateTime.tryParse(
        response['expires_at']?.toString() ?? '',
      );
    } on ApiException catch (exception) {
      error = exception.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> loadSkinCatalog({
    String query = '',
    String category = '',
    String weapon = '',
    String tier = '',
    String sort = 'name_asc',
  }) async {
    skinCatalogLoading = true;
    notifyListeners();
    try {
      final parameters = <String, String>{
        'q': query.trim(),
        'category': category,
        'weapon': weapon,
        'tier': tier,
        'sort': sort,
        'limit': '100',
      };
      final uri = Uri(
        path: '/valorant/skins/catalog',
        queryParameters: parameters,
      );
      skinCatalog = SkinCatalog.fromJson(await api.get(uri.toString()));
    } on ApiException catch (exception) {
      error = exception.message;
    } finally {
      skinCatalogLoading = false;
      notifyListeners();
    }
  }

  Future<void> addWatch(String itemId) async {
    await api.post(
      '/valorant/skins/watchlist',
      body: {'item_id': itemId, 'notify_enabled': true},
    );
    await _loadWatchData();
    notifyListeners();
  }

  Future<void> removeWatch(String itemId) async {
    await api.delete('/valorant/skins/watchlist/$itemId');
    await _loadWatchData();
    notifyListeners();
  }

  Future<String> sendTestNotification() async {
    loading = true;
    error = '';
    notifyListeners();
    try {
      await _pushService.register(api);
      final response = await api.post('/notifications/test');
      final sentCount = (response['sent_count'] as num?)?.toInt() ?? 0;
      final deviceCount = (response['device_count'] as num?)?.toInt() ?? 0;
      if (sentCount > 0) {
        return 'Notificação enviada. Ela deve aparecer em alguns segundos.';
      }
      if (deviceCount == 0) {
        return 'Nenhum aparelho registrado. Permita as notificações e tente novamente.';
      }
      return 'O Firebase não conseguiu entregar o teste. Tente novamente em instantes.';
    } on ApiException catch (exception) {
      error = exception.message;
      return exception.message;
    } on Object {
      return 'Não foi possível registrar as notificações neste aparelho.';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> updateProfile(String displayName) async {
    await api.patch('/me', body: {'display_name': displayName.trim()});
    me = MeData.fromJson(await api.get('/me'));
    notifyListeners();
  }
}

Map<String, dynamic> _map(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<dynamic> _list(dynamic value) => value is List ? value : const [];
