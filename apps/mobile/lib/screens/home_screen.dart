import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'account_screen.dart';
import 'link_screen.dart';
import 'notifications_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final rank = state.player?.competitive;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        color: ValcompColors.red,
        backgroundColor: ValcompColors.surface,
        onRefresh: state.refreshAll,
        child: PageFrame(
          topPadding: 24,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Olá, ${state.displayName}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 23,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  CircleAction(
                    icon: Icons.notifications_none_rounded,
                    badge: state.deliveries.isNotEmpty,
                    onTap: () => Navigator.push(
                      context,
                      valcompRoute(const NotificationsScreen()),
                    ),
                  ),
                  const SizedBox(width: 10),
                  CircleAction(
                    icon: Icons.person_outline_rounded,
                    onTap: () => Navigator.push(
                      context,
                      valcompRoute(const AccountScreen()),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 28),
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      title: 'Meu rank',
                      value: rank == null || !state.linked
                          ? '--'
                          : '${rank.rankedRating} RR',
                      subtitle: rank?.tierName,
                      imageUrl: rank?.tierIcon,
                      onTap: () => state.selectTab(2),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _MetricCard(
                      title: 'Alertas ativos',
                      value: '${state.watches.length}',
                      subtitle: state.watches.isEmpty
                          ? 'Nenhuma skin'
                          : 'skins monitoradas',
                      icon: Icons.notifications_active_outlined,
                      onTap: () => Navigator.push(
                        context,
                        valcompRoute(const NotificationsScreen()),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              _StoreBanner(onTap: () => state.selectTab(0)),
              const SizedBox(height: 22),
              _StatusFeature(state: state),
              if (state.error.isNotEmpty) ...[
                const SizedBox(height: 18),
                Text(
                  state.error,
                  style: const TextStyle(color: ValcompColors.red),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.onTap,
    this.subtitle,
    this.icon,
    this.imageUrl,
  });

  final String title;
  final String value;
  final String? subtitle;
  final IconData? icon;
  final String? imageUrl;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: ValcompColors.surface,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: SizedBox(
          height: 132,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(17, 16, 14, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const Icon(Icons.chevron_right_rounded, size: 19),
                  ],
                ),
                const Spacer(),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    if (imageUrl?.isNotEmpty == true)
                      Padding(
                        padding: const EdgeInsets.only(right: 9),
                        child: CachedNetworkImage(
                          imageUrl: imageUrl!,
                          width: 34,
                          height: 34,
                          errorWidget: (_, __, ___) => const SizedBox.shrink(),
                        ),
                      )
                    else if (icon != null)
                      Padding(
                        padding: const EdgeInsets.only(right: 9),
                        child: Icon(icon, size: 27),
                      ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            height: 27,
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: Text(
                                value,
                                maxLines: 1,
                                style: const TextStyle(
                                  fontSize: 24,
                                  height: 1,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ),
                          if (subtitle?.isNotEmpty == true)
                            Text(
                              subtitle!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: ValcompColors.muted,
                                fontSize: 10.5,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StoreBanner extends StatelessWidget {
  const _StoreBanner({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: ValcompColors.surface,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          height: 154,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            image: const DecorationImage(
              image: AssetImage('assets/images/store-gun.png'),
              fit: BoxFit.cover,
            ),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: Stack(
              fit: StackFit.expand,
              children: [
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Colors.transparent, Color(0xD9000000)],
                    ),
                  ),
                ),
                const Positioned(
                  right: 22,
                  bottom: 19,
                  child: Row(
                    children: [
                      Text(
                        'Ver minha loja',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      SizedBox(width: 5),
                      Icon(Icons.chevron_right_rounded),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StatusFeature extends StatelessWidget {
  const _StatusFeature({required this.state});

  final AppController state;

  @override
  Widget build(BuildContext context) {
    final linked = state.linked;
    final latest = state.player?.recentMatches.firstOrNull;
    final title = !linked
        ? (state.relinkRequired
              ? 'Sua sessão Riot expirou'
              : 'Vincule sua conta Riot')
        : latest != null
        ? 'Atividade recente'
        : 'Sua conta está conectada';
    final body = !linked
        ? 'Use o Valcomp Companion no computador onde você joga. O vínculo é feito uma única vez.'
        : latest != null
        ? '${_queueName(latest.queueId)} • ${_date(latest.startedAt)}'
        : 'A loja e os alertas estão prontos para consultar os dados disponíveis.';
    return Material(
      color: ValcompColors.surface,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        onTap: !linked
            ? () => Navigator.push(context, valcompRoute(const LinkScreen()))
            : () => state.selectTab(2),
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          height: 292,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            image: const DecorationImage(
              image: AssetImage('assets/images/hero-agent.png'),
              fit: BoxFit.cover,
              alignment: Alignment.topCenter,
            ),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: Stack(
              fit: StackFit.expand,
              children: [
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Color(0x22000000),
                        Color(0xBB000000),
                        Color(0xF5000000),
                      ],
                      stops: [0, 0.62, 1],
                    ),
                  ),
                ),
                Positioned(
                  left: 24,
                  right: 58,
                  bottom: 24,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        body,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xBFFFFFFF),
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                const Positioned(
                  right: 20,
                  bottom: 34,
                  child: Icon(Icons.chevron_right_rounded, size: 34),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _queueName(String queue) {
  return switch (queue.toLowerCase()) {
    'competitive' => 'Competitivo',
    'unrated' => 'Sem classificação',
    'swiftplay' => 'Disputa da Spike',
    'deathmatch' => 'Mata-mata',
    _ => queue.isEmpty ? 'Partida' : queue,
  };
}

String _date(DateTime? date) {
  if (date == null) return 'data indisponível';
  return DateFormat("dd/MM 'às' HH:mm", 'pt_BR').format(date.toLocal());
}
