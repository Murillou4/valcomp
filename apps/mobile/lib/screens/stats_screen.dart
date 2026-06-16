import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'link_screen.dart';
import 'match_details_screen.dart';

class StatsScreen extends StatelessWidget {
  const StatsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final summary = state.player;
    final rank = summary?.competitive;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        color: ValcompColors.red,
        backgroundColor: ValcompColors.surface,
        onRefresh: state.refreshAll,
        child: PageFrame(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Estatísticas',
                style: TextStyle(
                  fontSize: 36,
                  height: 1,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                state.me?.riotAccount?.riotId ?? 'Dados competitivos da conta',
                style: const TextStyle(color: ValcompColors.muted),
              ),
              const SizedBox(height: 28),
              if (!state.linked)
                EmptyCard(
                  icon: Icons.query_stats_rounded,
                  title: 'Estatísticas bloqueadas',
                  body:
                      'Vincule a conta Riot para consultar rank, RR e histórico disponíveis.',
                  action: 'Vincular conta',
                  onAction: () =>
                      Navigator.push(context, valcompRoute(const LinkScreen())),
                )
              else if (summary == null)
                state.playerError.isNotEmpty
                    ? EmptyCard(
                        icon: Icons.cloud_off_rounded,
                        title: 'Não foi possível atualizar as estatísticas',
                        body: state.playerError,
                        copyText: state.playerErrorDetails,
                        action: 'Tentar novamente',
                        onAction: state.refreshAll,
                      )
                    : const SizedBox(child: _StatsSkeleton())
              else ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(26),
                  decoration: BoxDecoration(
                    color: ValcompColors.surface,
                    borderRadius: BorderRadius.circular(28),
                    border: Border.all(color: ValcompColors.border),
                  ),
                  child: Row(
                    children: [
                      if (rank!.tierIcon.isNotEmpty)
                        CachedNetworkImage(
                          imageUrl: rank.tierIcon,
                          width: 92,
                          height: 92,
                          errorWidget: (_, __, ___) =>
                              const Icon(Icons.shield_outlined, size: 72),
                        ),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              rank.tierName,
                              style: const TextStyle(
                                fontSize: 23,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              '${rank.rankedRating} RR',
                              style: const TextStyle(
                                color: ValcompColors.red,
                                fontSize: 34,
                                height: 1,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 7),
                            Text(
                              rank.rrEarned == 0
                                  ? 'Última variação indisponível'
                                  : '${rank.rrEarned > 0 ? '+' : ''}${rank.rrEarned} RR na última atualização',
                              style: const TextStyle(
                                color: ValcompColors.muted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: _StatTile(
                        label: 'Vitórias',
                        value: '${rank.wins}',
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: _StatTile(
                        label: 'Partidas',
                        value: '${rank.games}',
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: _StatTile(
                        label: 'Win rate',
                        value: rank.games > 0
                            ? '${(rank.wins / rank.games * 100).round()}%'
                            : '--',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 30),
                const SectionHeader(title: 'Partidas recentes'),
                const SizedBox(height: 10),
                if (summary.recentMatches.isEmpty)
                  const EmptyCard(
                    icon: Icons.history_rounded,
                    title: 'Sem histórico disponível',
                    body:
                        'A Riot não retornou partidas recentes para esta conta.',
                  )
                else
                  ...summary.recentMatches
                      .take(10)
                      .map(
                        (match) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () => Navigator.push(
                                context,
                                valcompRoute(MatchDetailsScreen(match: match)),
                              ),
                              borderRadius: BorderRadius.circular(18),
                              child: Ink(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 18,
                                  vertical: 16,
                                ),
                                decoration: BoxDecoration(
                                  color: ValcompColors.surface,
                                  borderRadius: BorderRadius.circular(18),
                                  border: Border.all(
                                    color: ValcompColors.border,
                                  ),
                                ),
                                child: Row(
                                  children: [
                                    Container(
                                      width: 42,
                                      height: 42,
                                      decoration: BoxDecoration(
                                        color: ValcompColors.red.withValues(
                                          alpha: 0.12,
                                        ),
                                        borderRadius: BorderRadius.circular(13),
                                      ),
                                      child: const Icon(
                                        Icons.sports_esports_outlined,
                                        color: ValcompColors.red,
                                      ),
                                    ),
                                    const SizedBox(width: 14),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            _queue(match.queueId),
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w800,
                                            ),
                                          ),
                                          Text(
                                            _date(match.startedAt),
                                            style: const TextStyle(
                                              color: ValcompColors.muted,
                                              fontSize: 12,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    const Icon(
                                      Icons.chevron_right_rounded,
                                      color: ValcompColors.muted,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatsSkeleton extends StatelessWidget {
  const _StatsSkeleton();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        SkeletonBlock(height: 146, radius: 24),
        SizedBox(height: 18),
        Row(
          children: [
            Expanded(child: SkeletonBlock(height: 94, radius: 20)),
            SizedBox(width: 14),
            Expanded(child: SkeletonBlock(height: 94, radius: 20)),
            SizedBox(width: 14),
            Expanded(child: SkeletonBlock(height: 94, radius: 20)),
          ],
        ),
        SizedBox(height: 30),
        SkeletonBlock(height: 76, radius: 18),
        SizedBox(height: 10),
        SkeletonBlock(height: 76, radius: 18),
      ],
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 94,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: ValcompColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: ValcompColors.muted)),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

String _queue(String value) => switch (value.toLowerCase()) {
  'competitive' => 'Competitivo',
  'unrated' => 'Sem classificação',
  'swiftplay' => 'Disputa da Spike',
  'deathmatch' => 'Mata-mata',
  'spikerush' => 'Disparada',
  _ => value.isEmpty ? 'Partida' : value,
};

String _date(DateTime? value) => value == null
    ? 'Horário indisponível'
    : DateFormat("dd/MM/yyyy 'às' HH:mm", 'pt_BR').format(value.toLocal());
