import 'dart:async';

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
  ApiClient? _api;

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

  Future<void> register(ApiClient api) async {
    if (kIsWeb ||
        defaultTargetPlatform != TargetPlatform.android ||
        !await initializeFirebase()) {
      return;
    }
    _api = api;
    if (!_initialized) {
      const android = AndroidInitializationSettings('@mipmap/ic_launcher');
      await _notifications.initialize(
        settings: const InitializationSettings(android: android),
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
    await _notifications.show(
      id: message.hashCode,
      title: notification.title,
      body: notification.body,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails(
          'skin_alerts',
          'Alertas de skins',
          channelDescription:
              'Avisa quando uma skin desejada aparece na sua loja.',
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
      ),
    );
  }
}
