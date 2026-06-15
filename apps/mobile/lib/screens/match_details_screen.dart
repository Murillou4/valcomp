import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/app_controller.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

class MatchDetailsScreen extends StatefulWidget {
  const MatchDetailsScreen({super.key, required this.match});

  final RecentMatch match;

  @override
  State<MatchDetailsScreen> createState() => _MatchDetailsScreenState();
}

class _MatchDetailsScreenState extends State<MatchDetailsScreen> {
  MatchDetails? _details;
  ApiException? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final details = await context.read<AppController>().getMatchDetails(
        widget.match.matchId,
      );
      if (!mounted) return;
      setState(() => _details = details);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 36,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppPageHeader(
                title: _details?.match.mapName ?? 'Detalhes da partida',
                subtitle: _details == null
                    ? 'Carregando placar e desempenho'
                    : '${_queue(_details!.match.queueId)} • ${_date(_details!.match.startedAt)}',
              ),
              const SizedBox(height: 24),
              if (_loading)
                const SizedBox(
                  height: 420,
                  child: Center(
                    child: CircularProgressIndicator(color: ValcompColors.red),
                  ),
                )
              else if (_error != null)
                EmptyCard(
                  icon: Icons.cloud_off_rounded,
                  title: 'Não foi possível abrir esta partida',
                  body: _error!.userMessage,
                  copyText: _error!.fullDetails,
                  action: 'Tentar novamente',
                  onAction: _load,
                )
              else if (_details != null)
                _MatchContent(details: _details!),
            ],
          ),
        ),
      ),
    );
  }
}

class _MatchContent extends StatelessWidget {
  const _MatchContent({required this.details});

  final MatchDetails details;

  @override
  Widget build(BuildContext context) {
    final match = details.match;
    final self = details.self;
    final firstTeam = details.teams.isEmpty ? null : details.teams.first;
    final secondTeam = details.teams.length < 2 ? null : details.teams[1];
    final won = self != null && match.winningTeam == self.teamId;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          height: 218,
          decoration: BoxDecoration(
            color: ValcompColors.surface,
            borderRadius: BorderRadius.circular(26),
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (match.mapSplash.isNotEmpty)
                CachedNetworkImage(
                  imageUrl: match.mapSplash,
                  fit: BoxFit.cover,
                  errorWidget: (_, __, ___) => const SizedBox.shrink(),
                ),
              const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Colors.transparent, Color(0xF2070B10)],
                    stops: [0.2, 1],
                  ),
                ),
              ),
              Positioned(
                left: 22,
                right: 22,
                bottom: 20,
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            self == null
                                ? 'PARTIDA CONCLUÍDA'
                                : won
                                ? 'VITÓRIA'
                                : 'DERROTA',
                            style: TextStyle(
                              color: won
                                  ? ValcompColors.green
                                  : ValcompColors.red,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 1.2,
                            ),
                          ),
                          const SizedBox(height: 5),
                          Text(
                            match.mapName,
                            style: const TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '${firstTeam?.roundsWon ?? 0} : ${secondTeam?.roundsWon ?? 0}',
                      style: const TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (self != null) ...[
          const SizedBox(height: 28),
          const SectionHeader(title: 'Seu desempenho'),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: ValcompColors.surface,
              borderRadius: BorderRadius.circular(24),
              border: Border.all(
                color: ValcompColors.red.withValues(alpha: 0.25),
              ),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    _AgentAvatar(player: self, size: 58),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            self.agentName,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          Text(
                            self.riotId,
                            style: const TextStyle(color: ValcompColors.muted),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '${self.stats.kills}/${self.stats.deaths}/${self.stats.assists}',
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    _Metric(label: 'ACS', value: _number(self.stats.acs)),
                    _Metric(label: 'K/D', value: _number(self.stats.kd)),
                    _Metric(
                      label: 'HS',
                      value: '${_number(self.stats.headshotPercent)}%',
                    ),
                    _Metric(
                      label: 'ADR',
                      value: _number(self.stats.averageDamagePerRound),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 28),
        const SectionHeader(title: 'Placar'),
        const SizedBox(height: 12),
        ..._teamOrder(details).map(
          (teamId) => _TeamScoreboard(
            teamId: teamId,
            won: match.winningTeam == teamId,
            players: details.players
                .where((player) => player.teamId == teamId)
                .toList(),
          ),
        ),
        if (details.rounds.isNotEmpty) ...[
          const SizedBox(height: 28),
          const SectionHeader(title: 'Rounds'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: details.rounds
                .map(
                  (round) => Tooltip(
                    message: round.result,
                    child: Container(
                      width: 38,
                      height: 38,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: round.winningTeam == 'Blue'
                            ? const Color(0xFF2E77D0)
                            : ValcompColors.red,
                        borderRadius: BorderRadius.circular(11),
                      ),
                      child: Text(
                        '${round.round}',
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
        ],
      ],
    );
  }
}

class _TeamScoreboard extends StatelessWidget {
  const _TeamScoreboard({
    required this.teamId,
    required this.won,
    required this.players,
  });

  final String teamId;
  final bool won;
  final List<MatchPlayer> players;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: won
              ? ValcompColors.green.withValues(alpha: 0.32)
              : ValcompColors.border,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 13, 16, 10),
            child: Row(
              children: [
                Text(
                  won ? 'VENCEDORES' : 'EQUIPE ${teamId.toUpperCase()}',
                  style: TextStyle(
                    color: won ? ValcompColors.green : ValcompColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.8,
                  ),
                ),
                const Spacer(),
                const Text(
                  'K / D / A     ACS',
                  style: TextStyle(
                    color: ValcompColors.muted,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          ...players.map(
            (player) => Container(
              color: player.isSelf
                  ? ValcompColors.red.withValues(alpha: 0.09)
                  : Colors.transparent,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  _AgentAvatar(player: player, size: 42),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          player.riotId,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        Text(
                          player.agentName,
                          style: const TextStyle(
                            color: ValcompColors.muted,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    '${player.stats.kills}/${player.stats.deaths}/${player.stats.assists}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  SizedBox(
                    width: 54,
                    child: Text(
                      _number(player.stats.acs),
                      textAlign: TextAlign.end,
                      style: const TextStyle(color: ValcompColors.muted),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AgentAvatar extends StatelessWidget {
  const _AgentAvatar({required this.player, required this.size});

  final MatchPlayer player;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: ValcompColors.surfaceRaised,
        borderRadius: BorderRadius.circular(size * 0.3),
      ),
      clipBehavior: Clip.antiAlias,
      child: player.agentIcon.isEmpty
          ? const Icon(Icons.person_outline_rounded)
          : CachedNetworkImage(
              imageUrl: player.agentIcon,
              fit: BoxFit.cover,
              errorWidget: (_, __, ___) =>
                  const Icon(Icons.person_outline_rounded),
            ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          Text(
            label,
            style: const TextStyle(color: ValcompColors.muted, fontSize: 11),
          ),
        ],
      ),
    );
  }
}

List<String> _teamOrder(MatchDetails details) {
  final ids = details.teams
      .map((team) => team.teamId)
      .where((id) => id.isNotEmpty)
      .toList();
  for (final player in details.players) {
    if (player.teamId.isNotEmpty && !ids.contains(player.teamId)) {
      ids.add(player.teamId);
    }
  }
  return ids;
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

String _number(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value.toStringAsFixed(1);
