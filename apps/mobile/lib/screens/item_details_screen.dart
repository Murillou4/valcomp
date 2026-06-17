import 'dart:math' as math;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
    await HapticFeedback.selectionClick();
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
              _WeaponInspect3D(
                image: widget.image,
                name: widget.name,
                color: color,
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
                icon: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 180),
                  child: _changingWatch
                      ? const SizedBox(
                          key: ValueKey('watch-loading'),
                          width: 19,
                          height: 19,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.2,
                            color: Colors.white,
                          ),
                        )
                      : Icon(
                          watched
                              ? Icons.notifications_off_outlined
                              : Icons.notifications_active_outlined,
                          key: ValueKey(watched),
                        ),
                ),
                label: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 180),
                  child: Text(
                    watched
                        ? 'Remover alerta desta skin'
                        : 'Avisar quando aparecer na loja',
                    key: ValueKey('watch-label-$watched'),
                  ),
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

class _WeaponInspect3D extends StatefulWidget {
  const _WeaponInspect3D({
    required this.image,
    required this.name,
    required this.color,
  });

  final String image;
  final String name;
  final Color color;

  @override
  State<_WeaponInspect3D> createState() => _WeaponInspect3DState();
}

class _WeaponInspect3DState extends State<_WeaponInspect3D>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  double _yaw = 0;
  double _pitch = 0;
  bool _dragging = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3600),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onPanStart: (_) {
        HapticFeedback.selectionClick();
        setState(() => _dragging = true);
      },
      onPanUpdate: (details) {
        setState(() {
          _yaw = (_yaw + details.delta.dx / 170).clamp(-0.55, 0.55).toDouble();
          _pitch = (_pitch - details.delta.dy / 260)
              .clamp(-0.24, 0.24)
              .toDouble();
        });
      },
      onPanEnd: (_) => setState(() => _dragging = false),
      child: Semantics(
        label: 'Visualização 3D da skin ${widget.name}',
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final idleYaw = _dragging
                ? 0.0
                : math.sin(_controller.value * math.pi * 2) * 0.045;
            final idlePitch = _dragging
                ? 0.0
                : math.cos(_controller.value * math.pi * 2) * 0.014;
            final yaw = _yaw + idleYaw;
            final pitch = _pitch + idlePitch;
            final sweep = (_controller.value * 1.5) % 1;
            final scale = 1.02 + (yaw.abs() + pitch.abs()) * 0.08;
            final transform = Matrix4.identity()
              ..setEntry(3, 2, 0.0014)
              ..rotateX(pitch)
              ..rotateY(yaw)
              ..rotateZ(yaw * -0.045)
              ..scaleByDouble(scale, scale, scale, 1);

            return Container(
              height: 272,
              width: double.infinity,
              decoration: BoxDecoration(
                color: ValcompColors.surface,
                borderRadius: BorderRadius.circular(28),
                border: Border.all(color: widget.color.withValues(alpha: 0.36)),
                image: const DecorationImage(
                  image: AssetImage('assets/images/store-armory-v3.png'),
                  fit: BoxFit.cover,
                  alignment: Alignment.center,
                ),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(28),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            ValcompColors.surface.withValues(alpha: 0.08),
                            widget.color.withValues(alpha: 0.18),
                            ValcompColors.background.withValues(alpha: 0.86),
                          ],
                          stops: const [0, 0.46, 1],
                        ),
                      ),
                    ),
                    CustomPaint(
                      painter: _InspectGridPainter(
                        color: widget.color,
                        progress: _controller.value,
                      ),
                    ),
                    Positioned(
                      left: 18,
                      top: 16,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: ValcompColors.background.withValues(
                            alpha: 0.66,
                          ),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.08),
                          ),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.threed_rotation_rounded, size: 15),
                            SizedBox(width: 6),
                            Text(
                              '3D',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Positioned(
                      left: 54 + yaw * 26,
                      right: 54 - yaw * 26,
                      bottom: 52 - pitch * 24,
                      child: Container(
                        height: 20,
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.42),
                          borderRadius: BorderRadius.circular(999),
                          boxShadow: [
                            BoxShadow(
                              color: widget.color.withValues(alpha: 0.18),
                              blurRadius: 34,
                              spreadRadius: 6,
                            ),
                          ],
                        ),
                      ),
                    ),
                    Center(
                      child: Transform(
                        alignment: Alignment.center,
                        transform: transform,
                        child: SizedBox(
                          height: 172,
                          width: double.infinity,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 28),
                            child: widget.image.isEmpty
                                ? const Icon(
                                    Icons.sports_esports_outlined,
                                    size: 82,
                                  )
                                : CachedNetworkImage(
                                    imageUrl: widget.image,
                                    fit: BoxFit.contain,
                                    placeholder: (_, __) => const Center(
                                      child: SizedBox(
                                        width: 42,
                                        height: 42,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2.4,
                                          color: ValcompColors.red,
                                        ),
                                      ),
                                    ),
                                    errorWidget: (_, __, ___) => const Icon(
                                      Icons.sports_esports_outlined,
                                      size: 82,
                                    ),
                                  ),
                          ),
                        ),
                      ),
                    ),
                    Positioned.fill(
                      child: IgnorePointer(
                        child: Transform.translate(
                          offset: Offset(-170 + sweep * 420, 0),
                          child: Transform.rotate(
                            angle: -0.28,
                            child: Center(
                              child: Container(
                                width: 58,
                                height: 420,
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    colors: [
                                      Colors.transparent,
                                      Colors.white.withValues(alpha: 0.08),
                                      Colors.transparent,
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _InspectGridPainter extends CustomPainter {
  const _InspectGridPainter({required this.color, required this.progress});

  final Color color;
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final gridPaint = Paint()
      ..color = color.withValues(alpha: 0.12)
      ..strokeWidth = 1;
    final horizon = size.height * 0.68;
    for (var i = 0; i < 8; i++) {
      final y = horizon + i * 10.0;
      canvas.drawLine(
        Offset(18 + i * 13, y),
        Offset(size.width - 18 - i * 13, y),
        gridPaint,
      );
    }
    for (var i = -5; i <= 5; i++) {
      final center = size.width / 2;
      canvas.drawLine(
        Offset(center, horizon),
        Offset(center + i * 58.0, size.height),
        gridPaint,
      );
    }

    final pulsePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = color.withValues(alpha: 0.18 + progress * 0.08);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(15, 15, size.width - 30, size.height - 30),
        const Radius.circular(24),
      ),
      pulsePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _InspectGridPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.progress != progress;
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
