import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import '../widgets/store_item_card.dart';
import 'item_details_screen.dart';

class WishlistScreen extends StatefulWidget {
  const WishlistScreen({super.key});

  @override
  State<WishlistScreen> createState() => _WishlistScreenState();
}

class _WishlistScreenState extends State<WishlistScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  bool _savedTab = false;
  String _category = '';
  String _weapon = '';
  String _tier = '';
  String _sort = 'name_asc';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _load() {
    context.read<AppController>().loadSkinCatalog(
      query: _search.text,
      category: _category,
      weapon: _weapon,
      tier: _tier,
      sort: _sort,
    );
  }

  void _onSearch(String _) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 320), _load);
    setState(() {});
  }

  void _selectCategory(String value) {
    setState(() {
      _category = value;
      final catalog = context.read<AppController>().skinCatalog;
      final selectedWeapon = catalog?.weapons
          .where((item) => item.id == _weapon)
          .firstOrNull;
      if (value.isNotEmpty && selectedWeapon?.category != value) _weapon = '';
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final catalog = state.skinCatalog;
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 32,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppPageHeader(
                title: 'Wishlist',
                subtitle: _savedTab
                    ? '${state.watches.length} skins monitoradas'
                    : 'Encontre a skin que você quer',
              ),
              const SizedBox(height: 22),
              _ModeSwitch(
                saved: _savedTab,
                watchedCount: state.watches.length,
                onChanged: (saved) => setState(() => _savedTab = saved),
              ),
              const SizedBox(height: 24),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 260),
                child: _savedTab
                    ? _SavedList(
                        key: const ValueKey('saved'),
                        watches: state.watches,
                      )
                    : _ExploreCatalog(
                        key: const ValueKey('explore'),
                        search: _search,
                        catalog: catalog,
                        loading: state.skinCatalogLoading,
                        category: _category,
                        weapon: _weapon,
                        tier: _tier,
                        sort: _sort,
                        watchedIds: state.watches
                            .map((watch) => watch.itemId)
                            .toSet(),
                        onSearch: _onSearch,
                        onClearSearch: () {
                          _search.clear();
                          _load();
                          setState(() {});
                        },
                        onCategory: _selectCategory,
                        onWeapon: (value) {
                          setState(() => _weapon = value);
                          _load();
                        },
                        onTier: (value) {
                          setState(() => _tier = value);
                          _load();
                        },
                        onSort: (value) {
                          setState(() => _sort = value);
                          _load();
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModeSwitch extends StatelessWidget {
  const _ModeSwitch({
    required this.saved,
    required this.watchedCount,
    required this.onChanged,
  });

  final bool saved;
  final int watchedCount;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: ValcompColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: ValcompColors.border),
      ),
      child: Row(
        children: [
          _ModeButton(
            active: !saved,
            icon: Icons.grid_view_rounded,
            label: 'Explorar',
            onTap: () => onChanged(false),
          ),
          _ModeButton(
            active: saved,
            icon: Icons.notifications_active_outlined,
            label: 'Monitoradas ($watchedCount)',
            onTap: () => onChanged(true),
          ),
        ],
      ),
    );
  }
}

class _ModeButton extends StatelessWidget {
  const _ModeButton({
    required this.active,
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final bool active;
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Material(
        color: active ? ValcompColors.surfaceRaised : Colors.transparent,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 18,
                color: active ? Colors.white : ValcompColors.muted,
              ),
              const SizedBox(width: 7),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: active ? Colors.white : ValcompColors.muted,
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ExploreCatalog extends StatelessWidget {
  const _ExploreCatalog({
    super.key,
    required this.search,
    required this.catalog,
    required this.loading,
    required this.category,
    required this.weapon,
    required this.tier,
    required this.sort,
    required this.watchedIds,
    required this.onSearch,
    required this.onClearSearch,
    required this.onCategory,
    required this.onWeapon,
    required this.onTier,
    required this.onSort,
  });

  final TextEditingController search;
  final SkinCatalog? catalog;
  final bool loading;
  final String category;
  final String weapon;
  final String tier;
  final String sort;
  final Set<String> watchedIds;
  final ValueChanged<String> onSearch;
  final VoidCallback onClearSearch;
  final ValueChanged<String> onCategory;
  final ValueChanged<String> onWeapon;
  final ValueChanged<String> onTier;
  final ValueChanged<String> onSort;

  @override
  Widget build(BuildContext context) {
    final weapons =
        catalog?.weapons
            .where((item) => category.isEmpty || item.category == category)
            .toList() ??
        const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: search,
          onChanged: onSearch,
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            hintText: 'Skin ou arma, ex.: Kuronami, Vandal',
            prefixIcon: const Icon(Icons.search_rounded),
            suffixIcon: search.text.isEmpty
                ? null
                : IconButton(
                    tooltip: 'Limpar busca',
                    onPressed: onClearSearch,
                    icon: const Icon(Icons.close_rounded),
                  ),
          ),
        ),
        const SizedBox(height: 20),
        const SectionHeader(title: 'Categorias'),
        const SizedBox(height: 10),
        SizedBox(
          height: 40,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              _FilterChip(
                label: 'Todas',
                selected: category.isEmpty,
                onTap: () => onCategory(''),
              ),
              ...?catalog?.categories.map(
                (item) => _FilterChip(
                  label: item.name,
                  selected: category == item.id,
                  onTap: () => onCategory(item.id),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 22),
        Row(
          children: [
            const Expanded(child: SectionHeader(title: 'Armas')),
            if (weapon.isNotEmpty)
              TextButton(
                onPressed: () => onWeapon(''),
                child: const Text('Limpar'),
              ),
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 94,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: weapons.length + 1,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (context, index) {
              if (index == 0) {
                return _WeaponCard(
                  name: 'Todas',
                  icon: '',
                  selected: weapon.isEmpty,
                  onTap: () => onWeapon(''),
                );
              }
              final item = weapons[index - 1];
              return _WeaponCard(
                name: item.name,
                icon: item.icon,
                selected: weapon == item.id,
                onTap: () => onWeapon(item.id),
              );
            },
          ),
        ),
        const SizedBox(height: 22),
        Row(
          children: [
            Expanded(
              child: _MenuFilter(
                icon: Icons.diamond_outlined,
                label: tier.isEmpty
                    ? 'Todas as raridades'
                    : catalog?.tiers
                              .where((item) => item.id == tier)
                              .firstOrNull
                              ?.name ??
                          'Raridade',
                items: [
                  const MapEntry('', 'Todas as raridades'),
                  ...?catalog?.tiers.map(
                    (item) => MapEntry(item.id, item.name),
                  ),
                ],
                selected: tier,
                onSelected: onTier,
              ),
            ),
            const SizedBox(width: 10),
            _MenuFilter(
              icon: Icons.sort_rounded,
              label: switch (sort) {
                'name_desc' => 'Z–A',
                'weapon' => 'Por arma',
                _ => 'A–Z',
              },
              items: const [
                MapEntry('name_asc', 'Nome A–Z'),
                MapEntry('name_desc', 'Nome Z–A'),
                MapEntry('weapon', 'Agrupar por arma'),
              ],
              selected: sort,
              onSelected: onSort,
              compact: true,
            ),
          ],
        ),
        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(
              child: Text(
                catalog == null ? 'Catálogo' : '${catalog!.total} skins',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            if (loading)
              const SizedBox.square(
                dimension: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: ValcompColors.red,
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        if (catalog == null && loading)
          const _CatalogSkeleton()
        else if (catalog?.items.isEmpty ?? true)
          const EmptyCard(
            icon: Icons.search_off_rounded,
            title: 'Nenhuma skin encontrada',
            body: 'Remova algum filtro ou tente outro nome.',
          )
        else
          ...catalog!.items.map(
            (item) => _CatalogItem(
              item: item,
              watched: watchedIds.contains(item.itemId),
            ),
          ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: selected ? ValcompColors.red : ValcompColors.surface,
        borderRadius: BorderRadius.circular(13),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(13),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 15),
            child: Center(
              child: Text(
                label,
                style: TextStyle(
                  color: selected ? Colors.white : ValcompColors.muted,
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _WeaponCard extends StatelessWidget {
  const _WeaponCard({
    required this.name,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String name;
  final String icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? ValcompColors.surfaceRaised : ValcompColors.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: 116,
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? ValcompColors.red : Colors.transparent,
              width: 1.4,
            ),
          ),
          child: Column(
            children: [
              Expanded(
                child: icon.isEmpty
                    ? Icon(
                        Icons.select_all_rounded,
                        color: selected
                            ? ValcompColors.red
                            : ValcompColors.muted,
                      )
                    : CachedNetworkImage(
                        imageUrl: icon,
                        fit: BoxFit.contain,
                        errorWidget: (_, __, ___) =>
                            const Icon(Icons.sports_esports_outlined),
                      ),
              ),
              const SizedBox(height: 5),
              Text(
                name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: selected ? Colors.white : ValcompColors.muted,
                  fontWeight: FontWeight.w800,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MenuFilter extends StatelessWidget {
  const _MenuFilter({
    required this.icon,
    required this.label,
    required this.items,
    required this.selected,
    required this.onSelected,
    this.compact = false,
  });

  final IconData icon;
  final String label;
  final List<MapEntry<String, String>> items;
  final String selected;
  final ValueChanged<String> onSelected;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      initialValue: selected,
      onSelected: onSelected,
      color: ValcompColors.surfaceRaised,
      itemBuilder: (_) => items
          .map(
            (item) => PopupMenuItem<String>(
              value: item.key,
              child: Row(
                children: [
                  Expanded(child: Text(item.value)),
                  if (item.key == selected)
                    const Icon(Icons.check_rounded, color: ValcompColors.red),
                ],
              ),
            ),
          )
          .toList(),
      child: Container(
        height: 48,
        padding: EdgeInsets.symmetric(horizontal: compact ? 13 : 15),
        decoration: BoxDecoration(
          color: ValcompColors.surface,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: ValcompColors.border),
        ),
        child: Row(
          mainAxisSize: compact ? MainAxisSize.min : MainAxisSize.max,
          children: [
            Icon(icon, size: 18, color: ValcompColors.muted),
            const SizedBox(width: 8),
            if (compact)
              Text(label, style: const TextStyle(fontWeight: FontWeight.w800))
            else
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            const SizedBox(width: 6),
            const Icon(Icons.expand_more_rounded, size: 18),
          ],
        ),
      ),
    );
  }
}

class _CatalogItem extends StatelessWidget {
  const _CatalogItem({required this.item, required this.watched});

  final SkinCatalogItem item;
  final bool watched;

  @override
  Widget build(BuildContext context) {
    final color = tierColors[item.tier] ?? ValcompColors.surfaceRaised;
    return Padding(
      padding: const EdgeInsets.only(bottom: 11),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => Navigator.push(
            context,
            valcompRoute(
              ItemDetailsScreen(
                itemId: item.itemId,
                name: item.name,
                image: item.displayIcon,
                tier: item.tier,
              ),
            ),
          ),
          borderRadius: BorderRadius.circular(20),
          child: Ink(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: ValcompColors.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: ValcompColors.border),
            ),
            child: Row(
              children: [
                Container(
                  width: 94,
                  height: 64,
                  padding: const EdgeInsets.all(7),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: CachedNetworkImage(
                    imageUrl: item.displayIcon,
                    fit: BoxFit.contain,
                    errorWidget: (_, __, ___) =>
                        const Icon(Icons.sports_esports_outlined),
                  ),
                ),
                const SizedBox(width: 13),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.name,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          height: 1.1,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '${item.weaponName} • ${item.categoryName}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: ValcompColors.muted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  tooltip: watched ? 'Skin monitorada' : 'Adicionar à wishlist',
                  onPressed: watched
                      ? null
                      : () =>
                            context.read<AppController>().addWatch(item.itemId),
                  style: IconButton.styleFrom(
                    backgroundColor: watched
                        ? ValcompColors.green.withValues(alpha: 0.12)
                        : ValcompColors.red,
                    foregroundColor: watched
                        ? ValcompColors.green
                        : Colors.white,
                  ),
                  icon: Icon(watched ? Icons.check_rounded : Icons.add_rounded),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SavedList extends StatelessWidget {
  const _SavedList({super.key, required this.watches});

  final List<SkinWatch> watches;

  @override
  Widget build(BuildContext context) {
    if (watches.isEmpty) {
      return const EmptyCard(
        icon: Icons.notifications_none_rounded,
        title: 'Sua wishlist está vazia',
        body:
            'Volte para Explorar, escolha uma arma e adicione a skin desejada.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'Skins monitoradas'),
        const SizedBox(height: 10),
        ...watches.map(
          (watch) => Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(15),
            decoration: BoxDecoration(
              color: ValcompColors.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: ValcompColors.border),
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
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                IconButton(
                  tooltip: 'Remover alerta',
                  onPressed: () =>
                      context.read<AppController>().removeWatch(watch.itemId),
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
    );
  }
}

class _CatalogSkeleton extends StatelessWidget {
  const _CatalogSkeleton();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(
        4,
        (index) => const SkeletonBlock(
          height: 92,
          radius: 20,
          margin: EdgeInsets.only(bottom: 11),
        ),
      ),
    );
  }
}
