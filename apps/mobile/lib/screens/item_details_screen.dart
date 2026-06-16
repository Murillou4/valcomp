import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/app_controller.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/store_item_card.dart';
import 'link_screen.dart';

class ItemDetailsScreen extends StatefulWidget {
  const ItemDetailsScreen({
    super.key,
    required this.itemId,
    required this.name,
    required this.image,
    required this.tier,
    this.knownPrice,
  });

  final String itemId;
  final String name;
  final String image;
  final String tier;
  final int? knownPrice;

  @override
  State<ItemDetailsScreen> createState() => _ItemDetailsScreenState();
}

class _ItemDetailsScreenState extends State<ItemDetailsScreen> {
  ItemStatus? _status;
  ApiException? _error;
  bool _loading = true;
  bool _changingWatch = false;

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
      final status = await context.read<AppController>().getItemStatus(
        widget.itemId,
      );
      if (mounted) setState(() => _status = status);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleWatch() async {
    final state = context.read<AppController>();
    final watched = state.watches.any((item) => item.itemId == widget.itemId);
    setState(() => _changingWatch = true);
    try {
      if (watched) {
        await state.removeWatch(widget.itemId);
      } else {
        await state.addWatch(widget.itemId);
      }
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.userMessage)));
    } finally {
      if (mounted) setState(() => _changingWatch = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final watched = state.watches.any((item) => item.itemId == widget.itemId);
    final color = tierColors[widget.tier] ?? const Color(0xFF44505D);
    final price = _status?.price ?? widget.knownPrice;
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 36,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppPageHeader(
                title: 'Detalhes da skin',
                subtitle: 'Disponibilidade e alerta',
              ),
              const SizedBox(height: 22),
              Container(
                height: 250,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: ValcompColors.surface,
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: ValcompColors.border),
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [
                      color.withValues(alpha: 0.85),
                      color.withValues(alpha: 0.08),
                      ValcompColors.surface,
                    ],
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(26),
                  child: widget.image.isEmpty
                      ? const Icon(Icons.sports_esports_outlined, size: 80)
                      : CachedNetworkImage(
                          imageUrl: widget.image,
                          fit: BoxFit.contain,
                          errorWidget: (_, __, ___) => const Icon(
                            Icons.sports_esports_outlined,
                            size: 80,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 22),
              Text(
                widget.name,
                style: const TextStyle(
                  fontSize: 27,
                  height: 1.08,
                  fontWeight: FontWeight.w900,
                ),
              ),
              if (price != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Image.asset(
                      'assets/images/vp-symbol.png',
                      width: 19,
                      height: 19,
                    ),
                    const SizedBox(width: 7),
                    Text(
                      '$price VP',
                      style: const TextStyle(
                        color: ValcompColors.muted,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 24),
              if (_loading)
                const _StatusSkeleton()
              else if (_error?.relinkRequired == true)
                EmptyCard(
                  icon: Icons.link_rounded,
                  title: 'Vincule sua conta para consultar',
                  body:
                      'O alerta pode ser salvo agora, mas inventário e loja exigem uma sessão Riot ativa.',
                  action: 'Vincular conta',
                  onAction: () =>
                      Navigator.push(context, valcompRoute(const LinkScreen())),
                  copyText: _error!.fullDetails,
                )
              else if (_error != null)
                EmptyCard(
                  icon: Icons.cloud_off_rounded,
                  title: 'Status temporariamente indisponível',
                  body: _error!.userMessage,
                  copyText: _error!.fullDetails,
                  action: 'Tentar novamente',
                  onAction: _load,
                )
              else if (_status != null)
                LayoutBuilder(
                  builder: (context, constraints) {
                    final width = constraints.maxWidth >= 330
                        ? (constraints.maxWidth - 20) / 3
                        : constraints.maxWidth;
                    return Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        SizedBox(
                          width: width,
                          child: _Availability(
                            icon: Icons.inventory_2_outlined,
                            label: 'Inventário',
                            value: _status!.owned
                                ? 'Você possui'
                                : 'Não possui',
                            active: _status!.owned,
                          ),
                        ),
                        SizedBox(
                          width: width,
                          child: _Availability(
                            icon: Icons.shopping_bag_outlined,
                            label: 'Loja diária',
                            value: _status!.inDailyStore
                                ? 'Disponível'
                                : 'Fora da loja',
                            active: _status!.inDailyStore,
                          ),
                        ),
                        SizedBox(
                          width: width,
                          child: _Availability(
                            icon: Icons.dark_mode_outlined,
                            label: 'Noturno',
                            value: _status!.inNightMarket
                                ? 'Disponível'
                                : 'Fora da loja',
                            active: _status!.inNightMarket,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: _changingWatch ? null : _toggleWatch,
                icon: Icon(
                  watched
                      ? Icons.notifications_off_outlined
                      : Icons.notifications_active_outlined,
                ),
                label: Text(
                  watched
                      ? 'Remover alerta desta skin'
                      : 'Avisar quando aparecer na loja',
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'O Valcomp verifica sua loja e evita enviar o mesmo alerta mais de uma vez por rotação.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: ValcompColors.muted,
                  fontSize: 12,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Availability extends StatelessWidget {
  const _Availability({
    required this.icon,
    required this.label,
    required this.value,
    required this.active,
  });

  final IconData icon;
  final String label;
  final String value;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 112,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: active
              ? ValcompColors.green.withValues(alpha: 0.35)
              : ValcompColors.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            size: 21,
            color: active ? ValcompColors.green : ValcompColors.muted,
          ),
          const Spacer(),
          Text(
            label,
            style: const TextStyle(color: ValcompColors.muted, fontSize: 10),
          ),
          Text(
            value,
            maxLines: 2,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _StatusSkeleton extends StatelessWidget {
  const _StatusSkeleton();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth >= 330
            ? (constraints.maxWidth - 20) / 3
            : constraints.maxWidth;
        return Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            SizedBox(width: width, child: const SkeletonBlock(height: 112)),
            SizedBox(width: width, child: const SkeletonBlock(height: 112)),
            SizedBox(width: width, child: const SkeletonBlock(height: 112)),
          ],
        );
      },
    );
  }
}
