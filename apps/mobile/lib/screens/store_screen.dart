import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/store_item_card.dart';
import 'link_screen.dart';
import 'item_details_screen.dart';
import 'wishlist_screen.dart';

class StoreScreen extends StatefulWidget {
  const StoreScreen({super.key});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  bool _night = false;

  void _selectNightMarket(AppController state) {
    setState(() => _night = true);
    state.loadNightMarket(force: true);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final items = _night
        ? state.nightMarket?.items ?? state.store?.nightMarket ?? const []
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
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
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
                      onTap: () => _selectNightMarket(state),
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
              else if ((state.loading && state.store == null) ||
                  (_night && state.nightMarketLoading && items.isEmpty))
                const _StoreSkeleton()
              else if (_night && state.nightMarketError.isNotEmpty)
                EmptyCard(
                  icon: Icons.cloud_off_rounded,
                  title: 'Não foi possível abrir o Mercado Noturno',
                  body: state.nightMarketError,
                  copyText: state.nightMarketErrorDetails,
                  action: 'Tentar novamente',
                  onAction: () => state.loadNightMarket(force: true),
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
                      ? 'O Mercado Noturno não está ativo para sua conta neste momento. Assim que a Riot liberar uma nova edição, as ofertas aparecerão aqui.'
                      : 'Puxe a tela para baixo para consultar novamente.',
                )
              else
                ...items.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 22),
                    child: StoreItemCard(
                      item: item,
                      onTap: () => Navigator.push(
                        context,
                        valcompRoute(
                          ItemDetailsScreen(
                            itemId: item.itemId,
                            name: item.name,
                            image: item.image,
                            tier: item.tier,
                            knownPrice: item.price,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              if (state.storeError.isNotEmpty && state.linked) ...[
                const SizedBox(height: 18),
                EmptyCard(
                  icon: Icons.cloud_off_rounded,
                  title: 'Não foi possível atualizar a loja',
                  body: state.storeError,
                  copyText: state.storeErrorDetails,
                  action: 'Tentar novamente',
                  onAction: state.refreshAll,
                ),
              ],
              if ((_night
                      ? state.nightMarket?.expiresAt ??
                            state.store?.nightMarketExpiresAt
                      : state.store?.expiresAt) !=
                  null)
                Center(
                  child: Text(
                    '${_night ? 'Termina' : 'Rotação'} em ${_remaining((_night ? state.nightMarket?.expiresAt ?? state.store?.nightMarketExpiresAt : state.store?.expiresAt)!)}',
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

class _StoreSkeleton extends StatelessWidget {
  const _StoreSkeleton();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        SkeletonBlock(height: 132, margin: EdgeInsets.only(bottom: 22)),
        SkeletonBlock(height: 132, margin: EdgeInsets.only(bottom: 22)),
        SkeletonBlock(height: 132, margin: EdgeInsets.only(bottom: 22)),
      ],
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
      onTap: () {
        Feedback.forTap(context);
        onTap();
      },
      child: Column(
        children: [
          AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 220),
            style: TextStyle(
              color: active ? Colors.white : ValcompColors.muted,
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
