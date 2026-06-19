import 'dart:async';
import 'dart:convert';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../firebase_options.dart';
import 'api_client.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await PushService.initializeFirebase();
}

class PushService {
  static final _notifications = FlutterLocalNotificationsPlugin();
  static bool _backgroundHandlerInstalled = false;
  static bool _initialized = false;
  StreamSubscription<String>? _tokenRefreshSubscription;
  StreamSubscription<RemoteMessage>? _openSubscription;
  final Set<String> _handledOpenIds = <String>{};
  ApiClient? _api;
  VoidCallback? _onOpenStore;
  VoidCallback? _onRiotRelinkRequired;

  static bool get configured =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static Future<bool> initializeFirebase() async {
    if (!configured) return false;
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );
    }
    return true;
  }

  static void installBackgroundHandler() {
    if (!configured || _backgroundHandlerInstalled) return;
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    _backgroundHandlerInstalled = true;
  }

  Future<void> register(
    ApiClient api, {
    VoidCallback? onOpenStore,
    VoidCallback? onRiotRelinkRequired,
  }) async {
    if (kIsWeb ||
        defaultTargetPlatform != TargetPlatform.android ||
        !await initializeFirebase()) {
      return;
    }
    _api = api;
    _onOpenStore = onOpenStore ?? _onOpenStore;
    _onRiotRelinkRequired = onRiotRelinkRequired ?? _onRiotRelinkRequired;
    if (!_initialized) {
      const android = AndroidInitializationSettings('ic_notification');
      await _notifications.initialize(
        settings: const InitializationSettings(android: android),
        onDidReceiveNotificationResponse: _handleLocalNotificationTap,
      );
      const channel = AndroidNotificationChannel(
        'skin_alerts',
        'Alertas de skins',
        description: 'Avisa quando uma skin desejada aparece na sua loja.',
        importance: Importance.high,
      );
      await _notifications
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.createNotificationChannel(channel);
      const accountChannel = AndroidNotificationChannel(
        'account_status',
        'Status da conta',
        description: 'Avisa quando é necessário entrar novamente na Riot.',
        importance: Importance.high,
      );
      await _notifications
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.createNotificationChannel(accountChannel);
      FirebaseMessaging.onMessage.listen(_showForegroundNotification);
      _initialized = true;
    }
    final messaging = FirebaseMessaging.instance;
    await messaging.setAutoInitEnabled(true);
    final permission = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    if (permission.authorizationStatus == AuthorizationStatus.denied) return;
    final token = await messaging.getToken();
    if (token != null) await _registerToken(token);
    _openSubscription ??= FirebaseMessaging.onMessageOpenedApp.listen(
      _handleRemoteMessageOpen,
    );
    final initialMessage = await messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleRemoteMessageOpen(initialMessage);
    }
    _tokenRefreshSubscription ??= messaging.onTokenRefresh.listen((
      refreshedToken,
    ) async {
      try {
        await _registerToken(refreshedToken);
      } on Object catch (error) {
        debugPrint('Falha ao atualizar token FCM: $error');
      }
    });
  }

  Future<void> _registerToken(String token) async {
    final api = _api;
    if (api == null || token.length < 20) return;
    final info = await PackageInfo.fromPlatform();
    final android = await DeviceInfoPlugin().androidInfo;
    await api.post(
      '/notifications/devices',
      body: {
        'push_token': token,
        'provider': 'fcm',
        'platform': 'android',
        'device_name': '${android.manufacturer} ${android.model}'.trim(),
        'app_version': '${info.version}+${info.buildNumber}',
      },
    );
  }

  Future<void> _showForegroundNotification(RemoteMessage message) async {
    final notification = message.notification;
    if (notification == null) return;
    _handleNotificationData(message.data);
    final relinkRequired =
        message.data['type']?.toString() == 'riot_relink_required';
    await _notifications.show(
      id: message.hashCode,
      title: notification.title,
      body: notification.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          relinkRequired ? 'account_status' : 'skin_alerts',
          relinkRequired ? 'Status da conta' : 'Alertas de skins',
          channelDescription: relinkRequired
              ? 'Avisa quando é necessário entrar novamente na Riot.'
              : 'Avisa quando uma skin desejada aparece na sua loja.',
          importance: Importance.high,
          priority: Priority.high,
          icon: 'ic_notification',
        ),
      ),
      payload: jsonEncode(message.data),
    );
  }

  void _handleRemoteMessageOpen(RemoteMessage message) {
    final id = message.messageId ?? message.sentTime?.toIso8601String() ?? '';
    if (id.isNotEmpty && !_handledOpenIds.add(id)) return;
    _handleNotificationData(message.data);
  }

  void _handleLocalNotificationTap(NotificationResponse response) {
    final payload = response.payload;
    if (payload == null || payload.isEmpty) return;
    try {
      final decoded = jsonDecode(payload);
      if (decoded is Map) {
        _handleNotificationData(Map<String, dynamic>.from(decoded));
      }
    } on FormatException {
      return;
    }
  }

  void _handleNotificationData(Map<String, dynamic> data) {
    final type = data['type']?.toString() ?? '';
    final route = data['route']?.toString() ?? data['screen']?.toString() ?? '';
    if (type == 'skin_store_match' || route == 'store') {
      _onOpenStore?.call();
    } else if (type == 'riot_relink_required' || route == 'riot_setup') {
      _onRiotRelinkRequired?.call();
    }
  }
}
