import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme.dart';

class PageFrame extends StatelessWidget {
  const PageFrame({
    super.key,
    required this.child,
    this.scrollable = true,
    this.bottomPadding = 124,
    this.topPadding = 24,
  });

  final Widget child;
  final bool scrollable;
  final double bottomPadding;
  final double topPadding;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final side = constraints.maxWidth < 380 ? 18.0 : 24.0;
        final padding = EdgeInsets.fromLTRB(
          side,
          topPadding,
          side,
          bottomPadding,
        );
        final body = scrollable
            ? CustomScrollView(
                physics: const BouncingScrollPhysics(
                  parent: AlwaysScrollableScrollPhysics(),
                ),
                slivers: [
                  SliverPadding(
                    padding: padding,
                    sliver: SliverToBoxAdapter(child: child),
                  ),
                ],
              )
            : Padding(padding: padding, child: child);
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: body,
          ),
        );
      },
    );
  }
}

class CircleAction extends StatelessWidget {
  const CircleAction({
    super.key,
    required this.icon,
    required this.onTap,
    this.badge = false,
    this.size = 50,
  });

  final IconData icon;
  final VoidCallback onTap;
  final bool badge;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Material(
          color: ValcompColors.surfaceRaised,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(18)),
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: onTap,
            child: SizedBox(
              width: size,
              height: size,
              child: Icon(icon, size: 25, color: ValcompColors.text),
            ),
          ),
        ),
        if (badge)
          const Positioned(
            right: 2,
            top: 1,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: ValcompColors.red,
                shape: BoxShape.circle,
              ),
              child: SizedBox(width: 9, height: 9),
            ),
          ),
      ],
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.action,
    this.onAction,
  });

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
        ),
        if (action != null)
          TextButton(
            onPressed: onAction,
            child: Text(
              action!,
              style: const TextStyle(
                color: ValcompColors.red,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
      ],
    );
  }
}

class EmptyCard extends StatelessWidget {
  const EmptyCard({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    this.action,
    this.onAction,
    this.copyText,
  });

  final IconData icon;
  final String title;
  final String body;
  final String? action;
  final VoidCallback? onAction;
  final String? copyText;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: ValcompColors.border),
      ),
      child: Column(
        children: [
          Icon(icon, color: ValcompColors.red, size: 32),
          const SizedBox(height: 14),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Text(
            body,
            textAlign: TextAlign.center,
            style: const TextStyle(color: ValcompColors.muted, height: 1.4),
          ),
          if (action != null) ...[
            const SizedBox(height: 18),
            FilledButton(onPressed: onAction, child: Text(action!)),
          ],
          if (copyText?.isNotEmpty == true) ...[
            const SizedBox(height: 10),
            TextButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: copyText!));
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Detalhes técnicos copiados.')),
                );
              },
              icon: const Icon(Icons.copy_rounded, size: 18),
              label: const Text('Copiar detalhes do erro'),
            ),
          ],
        ],
      ),
    );
  }
}

class ErrorNotice extends StatelessWidget {
  const ErrorNotice({super.key, required this.message, this.details});

  final String message;
  final String? details;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
      decoration: BoxDecoration(
        color: ValcompColors.red.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: ValcompColors.red.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.error_outline_rounded,
            color: ValcompColors.red,
            size: 20,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: ValcompColors.red, height: 1.3),
            ),
          ),
          if (details?.isNotEmpty == true)
            IconButton(
              tooltip: 'Copiar detalhes do erro',
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: details!));
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Detalhes técnicos copiados.')),
                );
              },
              icon: const Icon(
                Icons.copy_rounded,
                color: ValcompColors.red,
                size: 19,
              ),
            ),
        ],
      ),
    );
  }
}

Route<T> valcompRoute<T>(Widget page) {
  return PageRouteBuilder<T>(
    transitionDuration: const Duration(milliseconds: 360),
    reverseTransitionDuration: const Duration(milliseconds: 260),
    pageBuilder: (_, animation, __) => FadeTransition(
      opacity: CurvedAnimation(parent: animation, curve: Curves.easeOut),
      child: page,
    ),
    transitionsBuilder: (_, animation, __, child) {
      final offset = Tween(
        begin: const Offset(0.05, 0),
        end: Offset.zero,
      ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOutCubic));
      return SlideTransition(position: offset, child: child);
    },
  );
}

class SkeletonBlock extends StatefulWidget {
  const SkeletonBlock({
    super.key,
    required this.height,
    this.width = double.infinity,
    this.radius = 18,
    this.margin,
  });

  final double height;
  final double width;
  final double radius;
  final EdgeInsetsGeometry? margin;

  @override
  State<SkeletonBlock> createState() => _SkeletonBlockState();
}

class _SkeletonBlockState extends State<SkeletonBlock>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final value = _controller.value;
        return Container(
          width: widget.width,
          height: widget.height,
          margin: widget.margin,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.radius),
            gradient: LinearGradient(
              begin: Alignment(-1.2 + value * 2.4, -0.7),
              end: Alignment(-0.2 + value * 2.4, 0.7),
              colors: const [
                ValcompColors.surface,
                ValcompColors.surfaceRaised,
                ValcompColors.surface,
              ],
            ),
            border: Border.all(color: ValcompColors.border),
          ),
        );
      },
    );
  }
}

class AppPageHeader extends StatelessWidget {
  const AppPageHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back_rounded),
          style: IconButton.styleFrom(
            backgroundColor: ValcompColors.surface,
            fixedSize: const Size(48, 48),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (subtitle != null)
                Text(
                  subtitle!,
                  style: const TextStyle(color: ValcompColors.muted),
                ),
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}
