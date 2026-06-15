import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/store_item_card.dart';

class WishlistScreen extends StatefulWidget {
  const WishlistScreen({super.key});

  @override
  State<WishlistScreen> createState() => _WishlistScreenState();
}

class _WishlistScreenState extends State<WishlistScreen> {
  final _search = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _onSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 350),
      () => context.read<AppController>().searchSkins(value),
    );
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final searching = _search.text.trim().length >= 2;
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 32,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppPageHeader(
                title: 'Wishlist',
                subtitle: 'Avise quando uma skin aparecer',
              ),
              const SizedBox(height: 28),
              TextField(
                controller: _search,
                onChanged: _onSearch,
                decoration: InputDecoration(
                  hintText: 'Buscar skin pelo nome',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: _search.text.isEmpty
                      ? null
                      : IconButton(
                          onPressed: () {
                            _search.clear();
                            state.searchSkins('');
                            setState(() {});
                          },
                          icon: const Icon(Icons.close_rounded),
                        ),
                ),
              ),
              const SizedBox(height: 24),
              if (searching) ...[
                Text(
                  state.skinResults.isEmpty
                      ? 'Nenhum resultado'
                      : '${state.skinResults.length} resultados',
                  style: const TextStyle(
                    color: ValcompColors.muted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                ...state.skinResults.map(
                  (item) => _SearchResult(
                    item: item,
                    watched: state.watches.any(
                      (watch) =>
                          watch.itemId ==
                          (item['levels'] is List &&
                                  (item['levels'] as List).isNotEmpty
                              ? (item['levels'] as List).first['uuid']
                              : item['uuid']),
                    ),
                  ),
                ),
              ] else ...[
                const SectionHeader(title: 'Skins monitoradas'),
                const SizedBox(height: 10),
                if (state.watches.isEmpty)
                  const EmptyCard(
                    icon: Icons.notifications_none_rounded,
                    title: 'Sua wishlist está vazia',
                    body:
                        'Busque uma skin acima. O backend compara sua wishlist com sua loja e envia o alerta.',
                  )
                else
                  ...state.watches.map(
                    (watch) => Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(15),
                      decoration: BoxDecoration(
                        color: ValcompColors.surface,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 82,
                            height: 54,
                            child: CachedNetworkImage(
                              imageUrl: watch.displayIcon,
                              fit: BoxFit.contain,
                              errorWidget: (_, __, ___) =>
                                  const Icon(Icons.sports_esports_outlined),
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Text(
                              watch.itemName,
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          IconButton(
                            tooltip: 'Remover alerta',
                            onPressed: () => state.removeWatch(watch.itemId),
                            icon: const Icon(
                              Icons.delete_outline_rounded,
                              color: ValcompColors.red,
                            ),
                          ),
                        ],
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

class _SearchResult extends StatelessWidget {
  const _SearchResult({required this.item, required this.watched});

  final Map<String, dynamic> item;
  final bool watched;

  @override
  Widget build(BuildContext context) {
    final levels = item['levels'] is List ? item['levels'] as List : const [];
    final itemId = levels.isNotEmpty
        ? (levels.first as Map)['uuid']?.toString() ?? ''
        : item['uuid']?.toString() ?? '';
    final image = item['displayIcon']?.toString() ?? '';
    final tier = item['contentTierUuid']?.toString() ?? '';
    final color = tierColors[tier] ?? ValcompColors.surfaceRaised;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Container(
            width: 88,
            height: 58,
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(14),
            ),
            child: CachedNetworkImage(
              imageUrl: image,
              fit: BoxFit.contain,
              errorWidget: (_, __, ___) =>
                  const Icon(Icons.sports_esports_outlined),
            ),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Text(
              item['displayName']?.toString() ?? 'Skin',
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          IconButton(
            onPressed: watched || itemId.isEmpty
                ? null
                : () => context.read<AppController>().addWatch(itemId),
            style: IconButton.styleFrom(
              backgroundColor: watched
                  ? ValcompColors.green.withValues(alpha: 0.12)
                  : ValcompColors.red,
              foregroundColor: watched ? ValcompColors.green : Colors.white,
            ),
            icon: Icon(watched ? Icons.check_rounded : Icons.add_rounded),
          ),
        ],
      ),
    );
  }
}
