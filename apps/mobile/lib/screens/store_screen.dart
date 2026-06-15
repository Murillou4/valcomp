import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/store_item_card.dart';
import 'link_screen.dart';
import 'wishlist_screen.dart';

class StoreScreen extends StatefulWidget {
  const StoreScreen({super.key});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  bool _night = false;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final items = _night
        ? state.store?.nightMarket ?? const []
        : state.store?.items ?? const [];
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
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Loja',
                      style: TextStyle(
                        fontFamily: 'Asgard',
                        fontSize: 37,
                        height: 1,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      valcompRoute(const WishlistScreen()),
                    ),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(0, 48),
                      padding: const EdgeInsets.symmetric(horizontal: 18),
                      shape: const StadiumBorder(),
                    ),
                    icon: const Icon(Icons.add_circle_outline_rounded),
                    label: const Text('Wishlist'),
                  ),
                ],
              ),
              const SizedBox(height: 34),
              Row(
                children: [
                  Expanded(
                    child: _StoreTab(
                      title: 'Mercado Diário',
                      active: !_night,
                      onTap: () => setState(() => _night = false),
                    ),
                  ),
                  Expanded(
                    child: _StoreTab(
                      title: 'Mercado Noturno',
                      active: _night,
                      onTap: () => setState(() => _night = true),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              if (!state.linked)
                EmptyCard(
                  icon: Icons.link_rounded,
                  title: state.relinkRequired
                      ? 'Vincule sua conta novamente'
                      : 'Conecte sua conta Riot',
                  body:
                      'A loja é privada e só pode ser consultada depois do vínculo pelo computador.',
                  action: 'Vincular conta',
                  onAction: () =>
                      Navigator.push(context, valcompRoute(const LinkScreen())),
                )
              else if (state.loading && state.store == null)
                const SizedBox(
                  height: 320,
                  child: Center(
                    child: CircularProgressIndicator(color: ValcompColors.red),
                  ),
                )
              else if (items.isEmpty)
                EmptyCard(
                  icon: _night
                      ? Icons.dark_mode_outlined
                      : Icons.shopping_bag_outlined,
                  title: _night
                      ? 'Mercado Noturno indisponível'
                      : 'Loja não carregada',
                  body: _night
                      ? 'Quando o Mercado Noturno estiver ativo na sua conta, os itens aparecerão aqui.'
                      : 'Puxe a tela para baixo para consultar novamente.',
                )
              else
                ...items.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 22),
                    child: StoreItemCard(item: item),
                  ),
                ),
              if (state.store?.expiresAt != null && items.isNotEmpty)
                Center(
                  child: Text(
                    'Rotação em ${_remaining(state.store!.expiresAt!)}',
                    style: const TextStyle(color: ValcompColors.muted),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StoreTab extends StatelessWidget {
  const _StoreTab({
    required this.title,
    required this.active,
    required this.onTap,
  });

  final String title;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Column(
        children: [
          AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 220),
            style: TextStyle(
              color: active ? Colors.white : ValcompColors.muted,
              fontFamily: 'Asgard',
              fontSize: 14,
              fontWeight: active ? FontWeight.w800 : FontWeight.w500,
            ),
            child: Text(title),
          ),
          const SizedBox(height: 9),
          AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            height: 2,
            width: active ? 96 : 0,
            color: Colors.white,
          ),
        ],
      ),
    );
  }
}

String _remaining(DateTime expiresAt) {
  final duration = expiresAt.difference(DateTime.now().toUtc());
  if (duration.isNegative) return 'alguns instantes';
  final hours = duration.inHours;
  final minutes = duration.inMinutes.remainder(60);
  return '${hours}h ${minutes}min';
}
