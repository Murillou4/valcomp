import 'package:device_info_plus/device_info_plus.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'api_client.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await PushService.initializeFirebase();
}

class PushService {
  static const _apiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const _appId = String.fromEnvironment('FIREBASE_APP_ID');
  static const _senderId = String.fromEnvironment(
    'FIREBASE_MESSAGING_SENDER_ID',
  );
  static const _projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  static final _notifications = FlutterLocalNotificationsPlugin();
  static bool _initialized = false;

  static bool get configured =>
      _apiKey.isNotEmpty &&
      _appId.isNotEmpty &&
      _senderId.isNotEmpty &&
      _projectId.isNotEmpty;

  static Future<bool> initializeFirebase() async {
    if (!configured) return false;
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(
        options: const FirebaseOptions(
          apiKey: _apiKey,
          appId: _appId,
          messagingSenderId: _senderId,
          projectId: _projectId,
        ),
      );
    }
    return true;
  }

  Future<void> register(ApiClient api) async {
    if (kIsWeb ||
        defaultTargetPlatform != TargetPlatform.android ||
        !await initializeFirebase()) {
      return;
    }
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
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
      FirebaseMessaging.onMessage.listen(_showForegroundNotification);
      _initialized = true;
    }
    final messaging = FirebaseMessaging.instance;
    final permission = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    if (permission.authorizationStatus == AuthorizationStatus.denied) return;
    final token = await messaging.getToken();
    if (token == null || token.length < 20) return;
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
