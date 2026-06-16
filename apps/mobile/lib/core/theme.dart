import 'package:flutter/material.dart';

abstract final class ValcompColors {
  static const background = Color(0xFF090E15);
  static const surface = Color(0xFF070B10);
  static const surfaceRaised = Color(0xFF101720);
  static const border = Color(0xFF1D2732);
  static const red = Color(0xFFFF4655);
  static const green = Color(0xFF65D6A3);
  static const amber = Color(0xFFF5C45B);
  static const text = Color(0xFFF7F8FA);
  static const muted = Color(0xFF919BA8);
}

ThemeData buildValcompTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: ValcompColors.red,
    brightness: Brightness.dark,
    surface: ValcompColors.surface,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: ValcompColors.background,
    splashFactory: InkSparkle.splashFactory,
    textTheme: const TextTheme(
      displaySmall: TextStyle(
        color: ValcompColors.text,
        fontSize: 36,
        height: 1,
        fontWeight: FontWeight.w700,
      ),
      headlineMedium: TextStyle(
        color: ValcompColors.text,
        fontSize: 24,
        height: 1.1,
        fontWeight: FontWeight.w800,
      ),
      titleLarge: TextStyle(
        color: ValcompColors.text,
        fontSize: 20,
        fontWeight: FontWeight.w700,
      ),
      titleMedium: TextStyle(
        color: ValcompColors.text,
        fontSize: 16,
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: TextStyle(
        color: ValcompColors.text,
        fontSize: 16,
        height: 1.35,
      ),
      bodyMedium: TextStyle(
        color: ValcompColors.muted,
        fontSize: 14,
        height: 1.4,
      ),
      labelLarge: TextStyle(
        color: ValcompColors.text,
        fontSize: 15,
        fontWeight: FontWeight.w700,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: ValcompColors.surface,
      hintStyle: const TextStyle(color: ValcompColors.muted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: ValcompColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: ValcompColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: ValcompColors.red, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: ValcompColors.red),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ValcompColors.red,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(56),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ValcompColors.text,
        minimumSize: const Size.fromHeight(52),
        side: const BorderSide(color: ValcompColors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: ValcompColors.text,
        textStyle: const TextStyle(fontWeight: FontWeight.w800),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        foregroundColor: ValcompColors.text,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: ValcompColors.surfaceRaised,
      contentTextStyle: const TextStyle(color: ValcompColors.text),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
  );
}
