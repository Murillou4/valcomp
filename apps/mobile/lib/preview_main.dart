import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

import 'core/app_controller.dart';
import 'core/models.dart';
import 'core/push_service.dart';
import 'core/theme.dart';
import 'screens/home_screen.dart';
import 'screens/item_details_screen.dart';
import 'screens/live_screen.dart';
import 'screens/wishlist_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('pt_BR');
  runApp(ValcompPreview(controller: PreviewController()));
}

class ValcompPreview extends StatelessWidget {
  const ValcompPreview({super.key, required this.controller});

  final PreviewController controller;

  @override
  Widget build(BuildContext context) {
    final screen = Uri.base.queryParameters['screen'];
    return ChangeNotifierProvider<AppController>.value(
      value: controller,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: buildValcompTheme(),
        home: Scaffold(
          body: switch (screen) {
            'wishlist' => const WishlistScreen(),
            'live' => const LiveScreen(),
            'item' => const ItemDetailsScreen(
              itemId: 'd980c0c8-492b-b8df-2d91-af99a7707170',
              name: 'Vandal Imortalizados',
              image:
                  'https://media.valorant-api.com/weaponskins/d980c0c8-492b-b8df-2d91-af99a7707170/displayicon.png',
              tier: _selectTier,
              knownPrice: 875,
            ),
            _ => const HomeScreen(),
          },
        ),
      ),
    );
  }
}

class PreviewController extends AppController {
  PreviewController() : super(pushService: PushService()) {
    booting = false;
    authenticated = true;
    me = const MeData(
      profile: Profile(userId: 'preview', displayName: 'Agente', avatarUrl: ''),
      riotAccount: RiotAccount(
        gameName: 'Preview',
        tagLine: 'BR1',
        region: 'br',
        shard: 'br',
      ),
    );
    player = PlayerSummary(
      available: true,
      competitive: const CompetitiveSummary(
        tier: 15,
        tierName: 'Platina 2',
        tierIcon:
            'https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350c805df75/15/largeicon.png',
        rankedRating: 96,
        rrEarned: 18,
        wins: 24,
        games: 43,
      ),
      recentMatches: [
        RecentMatch(
          matchId: 'preview',
          queueId: 'competitive',
          startedAt: DateTime.now().subtract(const Duration(hours: 2)),
        ),
      ],
      totalMatches: 43,
    );
    watches = const [
      SkinWatch(
        itemId: 'e5490f71-455b-74ad-f762-f5a876d4dff9',
        itemName: 'Vandal RGX 11z Pro',
        displayIcon:
            'https://media.valorant-api.com/weaponskins/e5490f71-455b-74ad-f762-f5a876d4dff9/displayicon.png',
        tier: 'e046854e-406c-37f4-6607-19a9ba8426fc',
        notifyEnabled: true,
      ),
    ];
    skinCatalog = _previewCatalog;
  }

  @override
  Future<void> loadSkinCatalog({
    String query = '',
    String category = '',
    String weapon = '',
    String tier = '',
    String sort = 'name_asc',
  }) async {}

  @override
  Future<void> addWatch(String itemId) async {
    final item = skinCatalog?.items
        .where((skin) => skin.itemId == itemId)
        .firstOrNull;
    if (item == null || watches.any((watch) => watch.itemId == itemId)) return;
    watches = [
      ...watches,
      SkinWatch(
        itemId: item.itemId,
        itemName: item.name,
        displayIcon: item.displayIcon,
        tier: item.tier,
        notifyEnabled: true,
      ),
    ];
    notifyListeners();
  }

  @override
  Future<void> removeWatch(String itemId) async {
    watches = watches.where((watch) => watch.itemId != itemId).toList();
    notifyListeners();
  }

  @override
  Future<ItemStatus> getItemStatus(String itemId) async {
    await Future<void>.delayed(const Duration(milliseconds: 260));
    return ItemStatus(
      itemId: itemId,
      owned: false,
      inDailyStore: true,
      inNightMarket: false,
      source: 'daily',
      price: 875,
      expiresAt: DateTime.now().toUtc().add(const Duration(hours: 11)),
    );
  }
}

const _selectTier = '12683d76-48d7-84a3-4e09-6985794f0445';
const _deluxeTier = '0cebb8be-46d7-c12a-d306-e9907bfc5a25';
const _exclusiveTier = 'e046854e-406c-37f4-6607-19a9ba8426fc';

const _previewCatalog = SkinCatalog(
  total: 6,
  categories: [
    CatalogFilter(id: 'rifle', name: 'Fuzis', count: 3),
    CatalogFilter(id: 'sidearm', name: 'Armas leves', count: 1),
    CatalogFilter(id: 'sniper', name: 'Fuzis de precisão', count: 1),
    CatalogFilter(id: 'smg', name: 'Submetralhadoras', count: 1),
  ],
  weapons: [
    CatalogFilter(
      id: '9c82e19d-4575-0200-1a81-3eacf00cf872',
      name: 'Vandal',
      count: 2,
      category: 'rifle',
      icon:
          'https://media.valorant-api.com/weapons/9c82e19d-4575-0200-1a81-3eacf00cf872/displayicon.png',
    ),
    CatalogFilter(
      id: 'ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a',
      name: 'Phantom',
      count: 1,
      category: 'rifle',
      icon:
          'https://media.valorant-api.com/weapons/ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a/displayicon.png',
    ),
    CatalogFilter(
      id: '1baa85b4-4c70-1284-64bb-6481dfc3bb4e',
      name: 'Ghost',
      count: 1,
      category: 'sidearm',
      icon:
          'https://media.valorant-api.com/weapons/1baa85b4-4c70-1284-64bb-6481dfc3bb4e/displayicon.png',
    ),
    CatalogFilter(
      id: 'a03b24d3-4319-996d-0f8c-94bbfba1dfc7',
      name: 'Operator',
      count: 1,
      category: 'sniper',
      icon:
          'https://media.valorant-api.com/weapons/a03b24d3-4319-996d-0f8c-94bbfba1dfc7/displayicon.png',
    ),
    CatalogFilter(
      id: '462080d1-4035-2937-7c09-27aa2a5c27a7',
      name: 'Spectre',
      count: 1,
      category: 'smg',
      icon:
          'https://media.valorant-api.com/weapons/462080d1-4035-2937-7c09-27aa2a5c27a7/displayicon.png',
    ),
  ],
  tiers: [
    CatalogFilter(
      id: _selectTier,
      name: 'Select Edition',
      count: 2,
      color: '#5A9FE2',
    ),
    CatalogFilter(
      id: _deluxeTier,
      name: 'Deluxe Edition',
      count: 1,
      color: '#009587',
    ),
    CatalogFilter(
      id: _exclusiveTier,
      name: 'Exclusive Edition',
      count: 3,
      color: '#F5955B',
    ),
  ],
  items: [
    SkinCatalogItem(
      itemId: 'e5490f71-455b-74ad-f762-f5a876d4dff9',
      name: 'Vandal RGX 11z Pro',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/e5490f71-455b-74ad-f762-f5a876d4dff9/displayicon.png',
      tier: _exclusiveTier,
      weaponId: '9c82e19d-4575-0200-1a81-3eacf00cf872',
      weaponName: 'Vandal',
      weaponIcon:
          'https://media.valorant-api.com/weapons/9c82e19d-4575-0200-1a81-3eacf00cf872/displayicon.png',
      category: 'rifle',
      categoryName: 'Fuzis',
    ),
    SkinCatalogItem(
      itemId: 'd980c0c8-492b-b8df-2d91-af99a7707170',
      name: 'Vandal Imortalizados',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/d980c0c8-492b-b8df-2d91-af99a7707170/displayicon.png',
      tier: _selectTier,
      weaponId: '9c82e19d-4575-0200-1a81-3eacf00cf872',
      weaponName: 'Vandal',
      weaponIcon:
          'https://media.valorant-api.com/weapons/9c82e19d-4575-0200-1a81-3eacf00cf872/displayicon.png',
      category: 'rifle',
      categoryName: 'Fuzis',
    ),
    SkinCatalogItem(
      itemId: '499acf05-4f79-e345-3714-57bf7aa163ea',
      name: 'Phantom RGX 11z Pro',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/499acf05-4f79-e345-3714-57bf7aa163ea/displayicon.png',
      tier: _exclusiveTier,
      weaponId: 'ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a',
      weaponName: 'Phantom',
      weaponIcon:
          'https://media.valorant-api.com/weapons/ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a/displayicon.png',
      category: 'rifle',
      categoryName: 'Fuzis',
    ),
    SkinCatalogItem(
      itemId: 'd0fbfdee-4961-cf51-24a4-4a853ee9fd0c',
      name: 'Ghost Esvoaçante',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/d0fbfdee-4961-cf51-24a4-4a853ee9fd0c/displayicon.png',
      tier: _selectTier,
      weaponId: '1baa85b4-4c70-1284-64bb-6481dfc3bb4e',
      weaponName: 'Ghost',
      weaponIcon:
          'https://media.valorant-api.com/weapons/1baa85b4-4c70-1284-64bb-6481dfc3bb4e/displayicon.png',
      category: 'sidearm',
      categoryName: 'Armas leves',
    ),
    SkinCatalogItem(
      itemId: '2e1936ed-4582-628f-da9c-25a7f47323cc',
      name: 'Operator RGX 11z Pro',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/2e1936ed-4582-628f-da9c-25a7f47323cc/displayicon.png',
      tier: _exclusiveTier,
      weaponId: 'a03b24d3-4319-996d-0f8c-94bbfba1dfc7',
      weaponName: 'Operator',
      weaponIcon:
          'https://media.valorant-api.com/weapons/a03b24d3-4319-996d-0f8c-94bbfba1dfc7/displayicon.png',
      category: 'sniper',
      categoryName: 'Fuzis de precisão',
    ),
    SkinCatalogItem(
      itemId: 'e78fb82c-4800-e102-b7a6-33946fa2f199',
      name: 'Spectre Força-Tarefa 809',
      displayIcon:
          'https://media.valorant-api.com/weaponskins/e78fb82c-4800-e102-b7a6-33946fa2f199/displayicon.png',
      tier: _deluxeTier,
      weaponId: '462080d1-4035-2937-7c09-27aa2a5c27a7',
      weaponName: 'Spectre',
      weaponIcon:
          'https://media.valorant-api.com/weapons/462080d1-4035-2937-7c09-27aa2a5c27a7/displayicon.png',
      category: 'smg',
      categoryName: 'Submetralhadoras',
    ),
  ],
);
