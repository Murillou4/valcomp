import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';
import 'package:valcomp/core/app_controller.dart';
import 'package:valcomp/core/models.dart';
import 'package:valcomp/core/theme.dart';
import 'package:valcomp/preview_main.dart';
import 'package:valcomp/screens/home_screen.dart';
import 'package:valcomp/screens/item_details_screen.dart';
import 'package:valcomp/screens/link_screen.dart';
import 'package:valcomp/screens/wishlist_screen.dart';
import 'package:valcomp/widgets/store_item_card.dart';

void main() {
  setUpAll(() => initializeDateFormatting('pt_BR'));

  Future<void> pumpScreen(
    WidgetTester tester,
    Widget screen, {
    Size size = const Size(360, 800),
  }) async {
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ChangeNotifierProvider<AppController>.value(
        value: PreviewController(),
        child: MaterialApp(
          theme: buildValcompTheme(),
          home: Scaffold(body: screen),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 500));
  }

  testWidgets('Home fits a compact Android viewport', (tester) async {
    await pumpScreen(tester, const HomeScreen());

    expect(find.text('96 RR'), findsOneWidget);
    expect(find.text('Ver minha loja'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Wishlist filters fit a compact Android viewport', (
    tester,
  ) async {
    await pumpScreen(tester, const WishlistScreen());

    expect(find.text('Explorar'), findsOneWidget);
    expect(find.text('Categorias'), findsOneWidget);
    expect(find.text('Armas'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Link screen exposes direct mobile Riot login', (tester) async {
    await pumpScreen(tester, const LinkScreen(), size: const Size(393, 852));

    expect(find.text('Entrar pela Riot neste celular'), findsOneWidget);
    expect(find.text('Mostrar opções avançadas'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Required Riot setup fits a compact Android viewport', (
    tester,
  ) async {
    await pumpScreen(
      tester,
      const LinkScreen(requiredSetup: true),
      size: const Size(360, 720),
    );

    expect(find.text('Configurar Riot'), findsOneWidget);
    expect(find.text('Entrar pela Riot neste celular'), findsOneWidget);
    expect(find.byIcon(Icons.logout_rounded), findsOneWidget);
    expect(find.byIcon(Icons.arrow_back_rounded), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Store names do not use the watermarked trial font', (
    tester,
  ) async {
    const item = StoreItem(
      itemId: 'phantom',
      name: 'Phantom RGX 11z Pro',
      displayIcon: '',
      fullRender: '',
      tier: '',
      source: 'daily',
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildValcompTheme(),
        home: const Scaffold(body: StoreItemCard(item: item)),
      ),
    );

    final text = tester.widget<Text>(find.text('PHANTOM RGX 11Z PRO'));
    expect(text.style?.fontFamily, isNot('Asgard'));
  });

  testWidgets('Item details status cards do not render layout errors', (
    tester,
  ) async {
    await pumpScreen(
      tester,
      const ItemDetailsScreen(
        itemId: 'd980c0c8-492b-b8df-2d91-af99a7707170',
        name: 'Vandal Imortalizados',
        image:
            'https://media.valorant-api.com/weaponskins/d980c0c8-492b-b8df-2d91-af99a7707170/displayicon.png',
        tier: '12683d76-48d7-84a3-4e09-6985794f0445',
        knownPrice: 875,
      ),
    );
    await tester.pump(const Duration(milliseconds: 600));

    expect(find.text('Loja diária'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
