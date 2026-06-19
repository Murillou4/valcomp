import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/live_models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

class LiveScreen extends StatelessWidget {
  const LiveScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final live = state.liveSnapshot;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        color: ValcompColors.red,
        backgroundColor: ValcompColors.surface,
        onRefresh: state.refreshLive,
        child: PageFrame(
          topPadding: 22,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Header(state: state),
              if (state.liveError.isNotEmpty) ...[
                const SizedBox(height: 12),
                ErrorNotice(message: state.liveError),
              ],
              if (state.liveCommandResult != null) ...[
                const SizedBox(height: 12),
                _CommandNotice(result: state.liveCommandResult!),
              ],
              const SizedBox(height: 22),
              _PhaseBody(state: state, live: live),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.state});
  final AppController state;

  @override
  Widget build(BuildContext context) {
    final live = state.liveSnapshot;
    final active = state.companionDevices
        .where((device) => device.active)
        .firstOrNull;
    final companionOnline = live.revision > 0
        ? live.online
        : active?.online == true;
    final basePresentation = _phasePresentation(live.phase);
    final presentation = live.phase == 'offline' && companionOnline
        ? (
            'Riot Client indisponível',
            live.state['message']?.toString().isNotEmpty == true
                ? live.state['message'].toString()
                : 'Abra o VALORANT para carregar o estado da partida.',
          )
        : basePresentation;
    final statusLabel = companionOnline
        ? 'PC CONECTADO'
        : active != null
        ? 'PC OFFLINE'
        : 'NÃO PAREADO';
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _StatusDot(online: companionOnline),
                  const SizedBox(width: 8),
                  Text(
                    statusLabel,
                    style: const TextStyle(
                      color: ValcompColors.muted,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                presentation.$1,
                style: const TextStyle(
                  fontSize: 27,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                presentation.$2,
                style: const TextStyle(color: ValcompColors.muted),
              ),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Atualizar estado',
          onPressed: state.liveLoading ? null : state.refreshLive,
          icon: const Icon(Icons.refresh_rounded),
          style: IconButton.styleFrom(
            backgroundColor: ValcompColors.surfaceRaised,
            fixedSize: const Size(48, 48),
          ),
        ),
      ],
    );
  }
}

class _CommandNotice extends StatelessWidget {
  const _CommandNotice({required this.result});
  final LiveCommandResult result;

  @override
  Widget build(BuildContext context) {
    final success = result.status == 'succeeded';
    final pending = result.status == 'queued' || result.status == 'delivered';
    final observed = result.result['observed'];
    final text = pending
        ? 'Ação enviada ao Companion.'
        : success && observed == true
        ? 'Alteração observada no cliente Riot.'
        : success
        ? 'A Riot aceitou a ação; aguardando confirmação visual.'
        : result.result['message']?.toString() ?? 'A ação não foi concluída.';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color:
            (success
                    ? ValcompColors.green
                    : pending
                    ? ValcompColors.amber
                    : ValcompColors.red)
                .withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(text, style: const TextStyle(fontSize: 12, height: 1.35)),
    );
  }
}

class _PhaseBody extends StatelessWidget {
  const _PhaseBody({required this.state, required this.live});
  final AppController state;
  final LiveSnapshot live;

  @override
  Widget build(BuildContext context) {
    return switch (live.phase) {
      'lobby' || 'queue' => _LobbyView(state: state, live: live),
      'match_found' || 'pregame' => _PregameView(state: state, live: live),
      'in_game' => _InGameView(state: state, live: live),
      'postgame' => _PostgameView(live: live),
      'client' => _ClientWaiting(state: state),
      _ => _OfflineView(state: state),
    };
  }
}

class _OfflineView extends StatelessWidget {
  const _OfflineView({required this.state});
  final AppController state;

  @override
  Widget build(BuildContext context) {
    final active = state.companionDevices
        .where((device) => device.active)
        .firstOrNull;
    final companionOnline = state.liveSnapshot.revision > 0
        ? state.liveSnapshot.online
        : active?.online == true;
    final code = state.companionPairCode;
    final riotMessage =
        state.liveSnapshot.state['message']?.toString() ??
        'Aguardando estado do Riot Client.';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle(
          title: active == null ? 'Conectar ao PC' : 'Seu computador',
        ),
        const SizedBox(height: 12),
        if (active == null && code == null)
          _SetupPanel(
            loading: state.liveLoading,
            onGenerate: state.generateCompanionPairCode,
          )
        else if (active == null && code != null)
          _PairCode(code: code)
        else if (active != null)
          _DeviceRow(
            device: active,
            online: companionOnline,
            onRemove: () => _confirmRemove(context, state, active),
          ),
        const SizedBox(height: 28),
        const _SectionTitle(title: 'Alertas'),
        const SizedBox(height: 10),
        _SoundToggle(state: state),
        const SizedBox(height: 28),
        const _SectionTitle(title: 'Diagnóstico'),
        const SizedBox(height: 10),
        _DiagnosticPanel(
          serverOnline: state.liveConnected,
          serverMessage: state.liveConnectionMessage,
          riotMessage: riotMessage,
          riotOnline: state.liveSnapshot.phase != 'offline',
          companionOnline: companionOnline,
          device: active,
        ),
        const SizedBox(height: 20),
        const _ExperimentalFooter(),
      ],
    );
  }

  Future<void> _confirmRemove(
    BuildContext context,
    AppController state,
    CompanionDevice device,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remover Companion?'),
        content: Text('${device.deviceName} perderá o acesso imediatamente.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remover'),
          ),
        ],
      ),
    );
    if (confirmed == true) await state.revokeCompanion(device.deviceId);
  }
}

class _SetupPanel extends StatelessWidget {
  const _SetupPanel({required this.loading, required this.onGenerate});
  final bool loading;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: ValcompColors.surface,
      border: Border.all(color: ValcompColors.border),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.desktop_windows_outlined, size: 28),
        const SizedBox(height: 16),
        const Text(
          'Pareie o Companion deste PC',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 5),
        const Text(
          'Gere um código e digite-o no aplicativo do Windows.',
          style: TextStyle(color: ValcompColors.muted, fontSize: 13),
        ),
        const SizedBox(height: 18),
        FilledButton.icon(
          onPressed: loading ? null : onGenerate,
          icon: const Icon(Icons.link_rounded),
          label: const Text('Gerar código'),
        ),
      ],
    ),
  );
}

class _DiagnosticPanel extends StatelessWidget {
  const _DiagnosticPanel({
    required this.serverOnline,
    required this.serverMessage,
    required this.riotMessage,
    required this.riotOnline,
    required this.companionOnline,
    required this.device,
  });
  final bool serverOnline;
  final String serverMessage;
  final String riotMessage;
  final bool riotOnline;
  final bool companionOnline;
  final CompanionDevice? device;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    decoration: BoxDecoration(
      color: ValcompColors.surface,
      border: Border.all(color: ValcompColors.border),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      children: [
        _DiagnosticItem(
          label: 'Servidor Valcomp',
          value: serverOnline ? 'Conectado' : serverMessage,
          online: serverOnline,
        ),
        _DiagnosticItem(
          label: 'Riot Client',
          value: riotMessage,
          online: riotOnline,
          last: device == null,
        ),
        if (device != null)
          _DiagnosticItem(
            label:
                'Companion ${device!.appVersion.isEmpty ? '' : device!.appVersion}',
            value: companionOnline ? 'Online agora' : 'PC offline',
            online: companionOnline,
            last: true,
          ),
      ],
    ),
  );
}

class _DiagnosticItem extends StatelessWidget {
  const _DiagnosticItem({
    required this.label,
    required this.value,
    required this.online,
    this.last = false,
  });
  final String label;
  final String value;
  final bool online;
  final bool last;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
    decoration: BoxDecoration(
      border: last
          ? null
          : const Border(bottom: BorderSide(color: ValcompColors.border)),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 5),
          child: _StatusDot(online: online),
        ),
        const SizedBox(width: 11),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                value,
                style: const TextStyle(
                  color: ValcompColors.muted,
                  fontSize: 12,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _ExperimentalFooter extends StatelessWidget {
  const _ExperimentalFooter();

  @override
  Widget build(BuildContext context) => const Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(Icons.info_outline_rounded, size: 16, color: ValcompColors.muted),
      SizedBox(width: 8),
      Expanded(
        child: Text(
          'Experimental e não aprovado pela Riot. Ações exigem confirmação manual.',
          style: TextStyle(
            color: ValcompColors.muted,
            fontSize: 11,
            height: 1.4,
          ),
        ),
      ),
    ],
  );
}

class _PairCode extends StatelessWidget {
  const _PairCode({required this.code});
  final CompanionPairCode code;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        border: Border.all(color: ValcompColors.border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'CÓDIGO DE 6 DÍGITOS',
            style: TextStyle(
              color: ValcompColors.muted,
              fontSize: 10,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Text(
                  code.code,
                  style: const TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 8,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Copiar código',
                onPressed: () =>
                    Clipboard.setData(ClipboardData(text: code.code)),
                icon: const Icon(Icons.copy_rounded),
              ),
            ],
          ),
          Text(
            'Válido até ${TimeOfDay.fromDateTime(code.expiresAt.toLocal()).format(context)}.',
            style: const TextStyle(color: ValcompColors.muted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class _DeviceRow extends StatelessWidget {
  const _DeviceRow({
    required this.device,
    required this.online,
    required this.onRemove,
  });
  final CompanionDevice device;
  final bool online;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: ValcompColors.border)),
      ),
      child: Row(
        children: [
          _StatusDot(online: online),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  device.deviceName,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                Text(
                  online ? 'Online agora' : 'Offline',
                  style: const TextStyle(
                    color: ValcompColors.muted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Remover Companion',
            onPressed: onRemove,
            icon: const Icon(
              Icons.delete_outline_rounded,
              color: ValcompColors.red,
            ),
          ),
        ],
      ),
    );
  }
}

class _SoundToggle extends StatelessWidget {
  const _SoundToggle({required this.state});
  final AppController state;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile.adaptive(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      tileColor: ValcompColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: ValcompColors.border),
        borderRadius: BorderRadius.circular(8),
      ),
      title: const Text(
        'Som de partida encontrada',
        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800),
      ),
      subtitle: const Text(
        'Som alto ao encontrar partida.',
        style: TextStyle(color: ValcompColors.muted, fontSize: 12),
      ),
      value: state.matchFoundSoundEnabled,
      activeTrackColor: ValcompColors.red,
      onChanged: state.setMatchFoundSound,
    );
  }
}

class _ClientWaiting extends StatelessWidget {
  const _ClientWaiting({required this.state});
  final AppController state;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const EmptyCard(
          icon: Icons.desktop_windows_outlined,
          title: 'VALORANT ainda não entrou no lobby',
          body: 'O Companion está conectado e aguardando uma sessão de jogo.',
        ),
        const SizedBox(height: 18),
        _SoundToggle(state: state),
      ],
    );
  }
}

class _LobbyView extends StatelessWidget {
  const _LobbyView({required this.state, required this.live});
  final AppController state;
  final LiveSnapshot live;

  @override
  Widget build(BuildContext context) {
    final queue = live.queue;
    final searching = live.phase == 'queue' || queue['searching'] == true;
    final selfId = live.state['account_id']?.toString();
    final self = live.members.where((item) => item['id'] == selfId).firstOrNull;
    final owner = self?['is_owner'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _QueueBand(queue: queue, searching: searching),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: state.liveLoading
                    ? null
                    : () => state.sendLiveCommand(
                        searching ? 'party.leave_queue' : 'party.join_queue',
                      ),
                icon: Icon(
                  searching ? Icons.stop_rounded : Icons.play_arrow_rounded,
                ),
                label: Text(searching ? 'Sair da fila' : 'Entrar na fila'),
              ),
            ),
            const SizedBox(width: 10),
            IconButton(
              tooltip: 'Alterar modo',
              onPressed: state.liveLoading
                  ? null
                  : () => _chooseQueue(context, state),
              icon: const Icon(Icons.tune_rounded),
              style: IconButton.styleFrom(
                backgroundColor: ValcompColors.surfaceRaised,
                fixedSize: const Size(56, 56),
              ),
            ),
          ],
        ),
        const SizedBox(height: 28),
        Row(
          children: [
            const Expanded(child: _SectionTitle(title: 'Party')),
            TextButton.icon(
              onPressed: state.liveLoading
                  ? null
                  : () => _invite(context, state),
              icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
              label: const Text('Convidar'),
            ),
          ],
        ),
        ...live.members.map(
          (member) => _MemberRow(
            member: member,
            isSelf: member['id'] == selfId,
            canRemove: owner && member['id'] != selfId,
            onRemove: () => state.sendLiveCommand('party.remove_member', {
              'puuid': member['id'],
            }),
          ),
        ),
        const SizedBox(height: 20),
        _PartyControls(state: state, live: live, self: self),
        const SizedBox(height: 22),
        _SoundToggle(state: state),
      ],
    );
  }

  Future<void> _chooseQueue(BuildContext context, AppController state) async {
    const queues = {
      'unrated': 'Sem classificação',
      'swiftplay': 'Disputa da Spike',
      'competitive': 'Competitivo',
      'spikerush': 'Spike Rush',
      'deathmatch': 'Mata-mata',
    };
    final queue = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: ValcompColors.surfaceRaised,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.symmetric(vertical: 12),
          children: queues.entries
              .map(
                (entry) => ListTile(
                  title: Text(entry.value),
                  onTap: () => Navigator.pop(context, entry.key),
                ),
              )
              .toList(),
        ),
      ),
    );
    if (queue != null) {
      await state.sendLiveCommand('party.change_queue', {'queue_id': queue});
    }
  }

  Future<void> _invite(BuildContext context, AppController state) async {
    final controller = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Convidar para o party'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 101,
          decoration: const InputDecoration(
            labelText: 'Riot ID',
            hintText: 'Nome#TAG',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Convidar'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value == null || !value.contains('#')) return;
    final parts = value.split('#');
    await state.sendLiveCommand('party.invite', {
      'game_name': parts.sublist(0, parts.length - 1).join('#'),
      'tag_line': parts.last,
    });
  }
}

class _QueueBand extends StatelessWidget {
  const _QueueBand({required this.queue, required this.searching});
  final Map<String, dynamic> queue;
  final bool searching;

  @override
  Widget build(BuildContext context) {
    final elapsed = (queue['elapsed_seconds'] as num?)?.toInt();
    final timer = elapsed == null
        ? '--:--'
        : '${(elapsed ~/ 60).toString().padLeft(2, '0')}:${(elapsed % 60).toString().padLeft(2, '0')}';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        border: Border.all(
          color: searching ? ValcompColors.red : ValcompColors.border,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            searching ? Icons.radar_rounded : Icons.groups_2_outlined,
            color: searching ? ValcompColors.red : ValcompColors.text,
            size: 30,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  searching ? 'BUSCANDO PARTIDA' : 'LOBBY',
                  style: const TextStyle(
                    color: ValcompColors.muted,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  queue['id']?.toString().isNotEmpty == true
                      ? queue['id'].toString()
                      : 'Modo indisponível',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
          Text(
            timer,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _MemberRow extends StatelessWidget {
  const _MemberRow({
    required this.member,
    required this.isSelf,
    required this.canRemove,
    required this.onRemove,
  });
  final Map<String, dynamic> member;
  final bool isSelf;
  final bool canRemove;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final rank = liveMap(member['rank']);
    final id = member['id']?.toString() ?? '';
    final fallback = id.length >= 4 ? id.substring(0, 4) : id;
    final gameName = member['game_name']?.toString() ?? '';
    return Container(
      constraints: const BoxConstraints(minHeight: 58),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: ValcompColors.border)),
      ),
      child: Row(
        children: [
          Icon(
            member['is_ready'] == true
                ? Icons.check_circle_rounded
                : Icons.circle_outlined,
            color: member['is_ready'] == true
                ? ValcompColors.green
                : ValcompColors.muted,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              isSelf
                  ? 'Você'
                  : gameName.isNotEmpty
                  ? gameName
                  : 'Membro $fallback',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Text(
            rank['name']?.toString().isNotEmpty == true
                ? rank['name'].toString()
                : 'Rank indisponível',
            style: const TextStyle(color: ValcompColors.muted, fontSize: 12),
          ),
          if (canRemove)
            IconButton(
              tooltip: 'Remover membro',
              onPressed: onRemove,
              icon: const Icon(Icons.person_remove_outlined, size: 20),
            ),
        ],
      ),
    );
  }
}

class _PartyControls extends StatelessWidget {
  const _PartyControls({required this.state, required this.live, this.self});
  final AppController state;
  final LiveSnapshot live;
  final Map<String, dynamic>? self;

  @override
  Widget build(BuildContext context) {
    final accessibility = live.party['accessibility']?.toString() ?? '';
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        ActionChip(
          avatar: Icon(
            self?['is_ready'] == true
                ? Icons.check_rounded
                : Icons.hourglass_empty_rounded,
            size: 18,
          ),
          label: Text(
            self?['is_ready'] == true ? 'Não estou pronto' : 'Estou pronto',
          ),
          onPressed: () => state.sendLiveCommand('party.set_ready', {
            'ready': self?['is_ready'] != true,
          }),
        ),
        ActionChip(
          avatar: const Icon(Icons.lock_outline_rounded, size: 18),
          label: Text(
            accessibility == 'OPEN' ? 'Party aberto' : 'Party fechado',
          ),
          onPressed: () => state.sendLiveCommand('party.set_accessibility', {
            'accessibility': accessibility == 'OPEN' ? 'CLOSED' : 'OPEN',
          }),
        ),
        ActionChip(
          avatar: const Icon(Icons.key_rounded, size: 18),
          label: const Text('Gerar código'),
          onPressed: () => state.sendLiveCommand('party.generate_code'),
        ),
      ],
    );
  }
}

class _PregameView extends StatelessWidget {
  const _PregameView({required this.state, required this.live});
  final AppController state;
  final LiveSnapshot live;

  @override
  Widget build(BuildContext context) {
    final map = live.map;
    final available = live.availableAgents;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _MapHeader(
          map: map,
          label: live.phase == 'match_found'
              ? 'PARTIDA ENCONTRADA'
              : 'SELEÇÃO DE AGENTE',
        ),
        if (live.phase == 'match_found' &&
            live.capabilities['match_accept'] == true) ...[
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: state.liveLoading
                ? null
                : () => state.sendLiveCommand('match.accept'),
            icon: const Icon(Icons.check_rounded),
            label: const Text('Aceitar partida'),
          ),
        ],
        const SizedBox(height: 24),
        const _SectionTitle(title: 'Escolhas do time'),
        const SizedBox(height: 10),
        SizedBox(
          height: 82,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: live.agents.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, index) => _AgentPortrait(
              agent: liveMap(live.agents[index]['agent']),
              selected: live.agents[index]['locked'] == true,
              width: 68,
            ),
          ),
        ),
        const SizedBox(height: 24),
        const _SectionTitle(title: 'Escolher agente'),
        const SizedBox(height: 12),
        if (available.isEmpty)
          const Text(
            'Catálogo de agentes indisponível no Companion.',
            style: TextStyle(color: ValcompColors.muted),
          )
        else
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 4,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
              childAspectRatio: 0.78,
            ),
            itemCount: available.length,
            itemBuilder: (context, index) {
              final agent = available[index];
              return _AgentPortrait(
                agent: agent,
                selected: state.selectedAgentId == agent['id'],
                onTap: state.liveLoading
                    ? null
                    : () => state.selectAgent(agent['id'].toString()),
              );
            },
          ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: state.selectedAgentId.isEmpty || state.liveLoading
              ? null
              : state.lockSelectedAgent,
          icon: const Icon(Icons.lock_rounded),
          label: const Text('Confirmar agente'),
        ),
        const SizedBox(height: 8),
        const Text(
          'O primeiro toque seleciona. O botão confirma o lock; não há escolha automática.',
          style: TextStyle(
            color: ValcompColors.muted,
            fontSize: 12,
            height: 1.4,
          ),
        ),
      ],
    );
  }
}

class _AgentPortrait extends StatelessWidget {
  const _AgentPortrait({
    required this.agent,
    required this.selected,
    this.onTap,
    this.width,
  });
  final Map<String, dynamic> agent;
  final bool selected;
  final VoidCallback? onTap;
  final double? width;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      width: width,
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: selected ? ValcompColors.red : ValcompColors.border,
          width: selected ? 2 : 1,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Expanded(
            child: agent['icon']?.toString().isNotEmpty == true
                ? CachedNetworkImage(
                    imageUrl: agent['icon'].toString(),
                    fit: BoxFit.cover,
                    width: double.infinity,
                    errorWidget: (_, _, _) =>
                        const Icon(Icons.person_outline_rounded),
                  )
                : const Center(child: Icon(Icons.person_outline_rounded)),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 5),
            child: Text(
              agent['name']?.toString().isNotEmpty == true
                  ? agent['name'].toString()
                  : 'Livre',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
    return onTap == null
        ? content
        : InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(6),
            child: content,
          );
  }
}

class _InGameView extends StatelessWidget {
  const _InGameView({required this.state, required this.live});
  final AppController state;
  final LiveSnapshot live;

  @override
  Widget build(BuildContext context) {
    final match = live.match;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _MapHeader(map: live.map, label: 'PARTIDA EM ANDAMENTO'),
        const SizedBox(height: 22),
        _ValueRow(
          label: 'Modo',
          value: liveMap(match['mode'])['name']?.toString().isNotEmpty == true
              ? liveMap(match['mode'])['name'].toString()
              : 'Indisponível',
        ),
        _ValueRow(
          label: 'Servidor',
          value: match['server']?.toString().isNotEmpty == true
              ? match['server'].toString()
              : 'Indisponível',
        ),
        _ValueRow(
          label: 'Placar',
          value: match['score']?.toString() ?? 'Indisponível',
        ),
        const SizedBox(height: 22),
        const _SectionTitle(title: 'Equipe'),
        const SizedBox(height: 10),
        SizedBox(
          height: 86,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: live.team.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, index) => _AgentPortrait(
              agent: liveMap(live.team[index]['agent']),
              selected: live.team[index]['is_self'] == true,
              width: 72,
            ),
          ),
        ),
        const SizedBox(height: 26),
        OutlinedButton.icon(
          onPressed: live.chatChannels.isEmpty
              ? null
              : () => _openChat(context, state, live.chatChannels),
          icon: const Icon(Icons.chat_bubble_outline_rounded),
          label: const Text('Enviar mensagem manual'),
        ),
        const SizedBox(height: 14),
        GestureDetector(
          onLongPress: state.liveLoading
              ? null
              : () => _confirmLeave(context, state),
          child: Container(
            width: double.infinity,
            height: 56,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              border: Border.all(
                color: ValcompColors.red.withValues(alpha: 0.55),
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.touch_app_rounded, color: ValcompColors.red),
                SizedBox(width: 8),
                Text(
                  'Segure para sair da partida',
                  style: TextStyle(
                    color: ValcompColors.red,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _openChat(
    BuildContext context,
    AppController state,
    List<Map<String, dynamic>> channels,
  ) async {
    final controller = TextEditingController();
    var selected = channels.first;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Mensagem manual'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                initialValue: selected['id']?.toString(),
                decoration: const InputDecoration(labelText: 'Canal'),
                items: channels
                    .map(
                      (channel) => DropdownMenuItem(
                        value: channel['id']?.toString(),
                        child: Text(channel['name']?.toString() ?? 'Chat'),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(
                  () => selected = channels.firstWhere(
                    (channel) => channel['id'] == value,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                maxLength: 280,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Mensagem'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'cid': selected['id'],
                'message': controller.text.trim(),
                'chat_type': 'groupchat',
              }),
              child: const Text('Enviar'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (result != null && result['message']?.toString().isNotEmpty == true) {
      await state.sendLiveCommand('chat.send', result);
    }
  }

  Future<void> _confirmLeave(BuildContext context, AppController state) async {
    HapticFeedback.heavyImpact();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sair da partida?'),
        content: const Text(
          'Esta ação pode gerar penalidade, perda de RR ou restrição de fila. O Valcomp não tentará novamente.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Continuar jogando'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sair mesmo assim'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await state.sendLiveCommand('current_game.leave', {'confirmed': true});
    }
  }
}

class _PostgameView extends StatelessWidget {
  const _PostgameView({required this.live});
  final LiveSnapshot live;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const EmptyCard(
          icon: Icons.flag_outlined,
          title: 'Partida encerrada',
          body:
              'Resultado e RR aparecerão quando a API da Riot liberar os dados finais.',
        ),
        const SizedBox(height: 18),
        _ValueRow(
          label: 'Resultado',
          value: live.state['result']?.toString() ?? 'Indisponível',
        ),
        _ValueRow(
          label: 'Variação de RR',
          value: live.state['rr_change']?.toString() ?? 'Indisponível',
        ),
      ],
    );
  }
}

class _MapHeader extends StatelessWidget {
  const _MapHeader({required this.map, required this.label});
  final Map<String, dynamic> map;
  final String label;

  @override
  Widget build(BuildContext context) {
    final icon = map['icon']?.toString() ?? '';
    final name = map['name']?.toString().isNotEmpty == true
        ? map['name'].toString()
        : 'Mapa indisponível';
    return SizedBox(
      width: double.infinity,
      height: 188,
      child: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: ValcompColors.surface,
              borderRadius: BorderRadius.circular(8),
            ),
            child: icon.isEmpty
                ? const Center(
                    child: Icon(
                      Icons.map_outlined,
                      size: 42,
                      color: ValcompColors.muted,
                    ),
                  )
                : ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: CachedNetworkImage(
                      imageUrl: icon,
                      fit: BoxFit.cover,
                      errorWidget: (_, _, _) =>
                          const Center(child: Icon(Icons.map_outlined)),
                    ),
                  ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: Colors.black.withValues(alpha: 0.34),
              ),
            ),
          ),
          Positioned(
            left: 16,
            right: 16,
            bottom: 16,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  name,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ValueRow extends StatelessWidget {
  const _ValueRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final stacked = value.length > 24;
    return Container(
      constraints: const BoxConstraints(minHeight: 48),
      padding: EdgeInsets.symmetric(vertical: stacked ? 11 : 0),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: ValcompColors.border)),
      ),
      child: stacked
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    color: ValcompColors.muted,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            )
          : Row(
              children: [
                Expanded(
                  child: Text(
                    label,
                    style: const TextStyle(color: ValcompColors.muted),
                  ),
                ),
                Flexible(
                  child: Text(
                    value,
                    textAlign: TextAlign.right,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) => Text(
    title,
    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
  );
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.online});
  final bool online;

  @override
  Widget build(BuildContext context) => Container(
    width: 9,
    height: 9,
    decoration: BoxDecoration(
      color: online ? ValcompColors.green : ValcompColors.muted,
      shape: BoxShape.circle,
    ),
  );
}

(String, String) _phasePresentation(String phase) => switch (phase) {
  'client' => ('Cliente conectado', 'Aguardando o lobby do VALORANT.'),
  'lobby' => ('No lobby', 'Party, fila e convites.'),
  'queue' => ('Buscando partida', 'O alerta tocará quando a partida aparecer.'),
  'match_found' => ('Partida encontrada', 'Confira o VALORANT para continuar.'),
  'pregame' => ('Seleção de agente', 'Selecione e confirme manualmente.'),
  'in_game' => ('Partida em andamento', 'Somente dados visíveis no cliente.'),
  'postgame' => ('Partida encerrada', 'Aguardando os dados finais.'),
  'error' => ('Estado indisponível', 'Confira o diagnóstico abaixo.'),
  _ => ('Companion offline', 'Pareie o PC ou abra o VALORANT.'),
};
