import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../widgets/bottom_nav.dart';
import '../widgets/update_banner.dart';
import 'home_screen.dart';
import 'live_screen.dart';
import 'stats_screen.dart';
import 'store_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  String _promptedVersion = '';

  static const _pages = [
    StoreScreen(key: ValueKey('store')),
    HomeScreen(key: ValueKey('home')),
    StatsScreen(key: ValueKey('stats')),
    LiveScreen(key: ValueKey('live')),
  ];

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    _scheduleUpdatePrompt(state);
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: Stack(
        children: [
          Positioned.fill(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              switchInCurve: Curves.easeOutCubic,
              transitionBuilder: (child, animation) {
                return FadeTransition(
                  opacity: animation,
                  child: SlideTransition(
                    position: Tween(
                      begin: const Offset(0.025, 0),
                      end: Offset.zero,
                    ).animate(animation),
                    child: child,
                  ),
                );
              },
              child: _pages[state.navIndex],
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: ValcompBottomNav(
              index: state.navIndex,
              onChanged: state.selectTab,
            ),
          ),
        ],
      ),
    );
  }

  void _scheduleUpdatePrompt(AppController state) {
    final info = state.updateInfo;
    if (info == null || info.latestLabel == _promptedVersion) return;
    _promptedVersion = info.latestLabel;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) showUpdatePrompt(context, info);
    });
  }
}
