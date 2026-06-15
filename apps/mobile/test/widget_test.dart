import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:valcomp/core/theme.dart';

void main() {
  testWidgets('Valcomp theme uses the expected dark background', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildValcompTheme(),
        home: const Scaffold(body: Text('Valcomp')),
      ),
    );

    expect(find.text('Valcomp'), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, isNull);
    expect(
      Theme.of(tester.element(find.text('Valcomp'))).scaffoldBackgroundColor,
      ValcompColors.background,
    );
  });
}
