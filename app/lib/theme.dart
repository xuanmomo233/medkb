import 'package:flutter/material.dart';
import 'api.dart';

/// 阅读字号（10~20，持久化于 Api）。修改请用 setFontSize。
final ValueNotifier<double> fontScale = ValueNotifier<double>(15);

Future<void> setFontSize(double v) async {
  fontScale.value = v;
  await Api.save(fontSize: v);
}

@immutable
class AppColors extends ThemeExtension<AppColors> {
  final Color good;
  final Color goodSoft;
  final Color bad;
  final Color badSoft;
  final Color warn;
  final Color warnSoft;
  final Color info;
  final Color infoSoft;

  const AppColors({
    required this.good,
    required this.goodSoft,
    required this.bad,
    required this.badSoft,
    required this.warn,
    required this.warnSoft,
    required this.info,
    required this.infoSoft,
  });

  static const AppColors light = AppColors(
    good: Color(0xFF16A34A),
    goodSoft: Color(0xFFDCFCE7),
    bad: Color(0xFFDC2626),
    badSoft: Color(0xFFFEE2E2),
    warn: Color(0xFFD97706),
    warnSoft: Color(0xFFFEF3C7),
    info: Color(0xFF2563EB),
    infoSoft: Color(0xFFDBEAFE),
  );

  static const AppColors dark = AppColors(
    good: Color(0xFF4ADE80),
    goodSoft: Color(0xFF12301F),
    bad: Color(0xFFF87171),
    badSoft: Color(0xFF3B1818),
    warn: Color(0xFFFBBF24),
    warnSoft: Color(0xFF3A2A0C),
    info: Color(0xFF60A5FA),
    infoSoft: Color(0xFF14284A),
  );

  static AppColors of(BuildContext context) =>
      Theme.of(context).extension<AppColors>() ??
      (Theme.of(context).brightness == Brightness.dark ? dark : light);

  @override
  AppColors copyWith({
    Color? good,
    Color? goodSoft,
    Color? bad,
    Color? badSoft,
    Color? warn,
    Color? warnSoft,
    Color? info,
    Color? infoSoft,
  }) {
    return AppColors(
      good: good ?? this.good,
      goodSoft: goodSoft ?? this.goodSoft,
      bad: bad ?? this.bad,
      badSoft: badSoft ?? this.badSoft,
      warn: warn ?? this.warn,
      warnSoft: warnSoft ?? this.warnSoft,
      info: info ?? this.info,
      infoSoft: infoSoft ?? this.infoSoft,
    );
  }

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(
      good: Color.lerp(good, other.good, t)!,
      goodSoft: Color.lerp(goodSoft, other.goodSoft, t)!,
      bad: Color.lerp(bad, other.bad, t)!,
      badSoft: Color.lerp(badSoft, other.badSoft, t)!,
      warn: Color.lerp(warn, other.warn, t)!,
      warnSoft: Color.lerp(warnSoft, other.warnSoft, t)!,
      info: Color.lerp(info, other.info, t)!,
      infoSoft: Color.lerp(infoSoft, other.infoSoft, t)!,
    );
  }
}

class AppTheme {
  AppTheme._();

  static const Color brand = Color(0xFF0F766E);
  static const Color brandDark = Color(0xFF2DD4BF);

  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness b) {
    final bool isDark = b == Brightness.dark;
    final Color primary = isDark ? brandDark : brand;
    final Color bg = isDark ? const Color(0xFF0E1319) : const Color(0xFFF6F8FA);
    final Color surface = isDark ? const Color(0xFF171E26) : Colors.white;
    final Color border =
        isDark ? const Color(0xFF263040) : const Color(0xFFE3E8EE);

    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: brand,
      brightness: b,
    ).copyWith(
      primary: primary,
      onPrimary: isDark ? const Color(0xFF042F2B) : Colors.white,
      surface: surface,
      outlineVariant: border,
    );

    final RoundedRectangleBorder cardShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: BorderSide(color: border),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: b,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      dividerColor: border,
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: cardShape,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        foregroundColor: isDark ? const Color(0xFFE6EDF3) : const Color(0xFF1F2937),
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        indicatorColor: primary.withOpacity(0.16),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
      extensions: <ThemeExtension<dynamic>>[
        isDark ? AppColors.dark : AppColors.light,
      ],
    );
  }
}
