import 'dart:async';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

import 'core/app_controller.dart';
import 'core/diagnostic_log.dart';
import 'core/push_service.dart';
import 'core/theme.dart';
import 'screens/app_shell.dart';
import 'screens/auth_screen.dart';
import 'screens/link_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await DiagnosticLog.instance.initialize();
  FlutterError.onError = (details) {
    FlutterError.presentError(details);
    unawaited(
      DiagnosticLog.instance.record(
        level: 'critical',
        category: 'flutter_error',
        message: details.exceptionAsString(),
        stackTrace: details.stack?.toString() ?? '',
        context: {
          'library': details.library ?? '',
          'context': '${details.context ?? ''}',
        },
      ),
    );
  };
  PlatformDispatcher.instance.onError = (error, stack) {
    unawaited(
      DiagnosticLog.instance.record(
        level: 'critical',
        category: 'platform_error',
        message: error.toString(),
        stackTrace: stack.toString(),
      ),
    );
    return true;
  };
  await initializeDateFormatting('pt_BR');
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  await PushService.initializeFirebase();
  PushService.installBackgroundHandler();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: ValcompColors.background,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  final controller = AppController(pushService: PushService());
  await controller.bootstrap();
  runApp(ValcompApp(controller: controller));
}

class ValcompApp extends StatelessWidget {
  const ValcompApp({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: controller,
      child: MaterialApp(
        title: 'Valcomp',
        debugShowCheckedModeBanner: false,
        theme: buildValcompTheme(),
        home: Consumer<AppController>(
          builder: (context, state, _) {
            return AnimatedSwitcher(
              duration: const Duration(milliseconds: 320),
              switchInCurve: Curves.easeOutCubic,
              switchOutCurve: Curves.easeInCubic,
              child: !state.authenticated
                  ? const AuthScreen(key: ValueKey('auth'))
                  : state.requiresRiotSetup
                  ? LinkScreen(
                      key: ValueKey(
                        state.relinkRequired ? 'riot-relink' : 'riot-setup',
                      ),
                      requiredSetup: true,
                    )
                  : const AppShell(key: ValueKey('app')),
            );
          },
        ),
      ),
    );
  }
}
