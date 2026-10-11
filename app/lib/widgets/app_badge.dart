import 'package:flutter/material.dart';
import '../theme.dart';

enum BadgeTone { neutral, primary, good, bad, warn, info }

/// 小标签（避免与 Material 的 Badge 重名，故命名为 AppBadge）
class AppBadge extends StatelessWidget {
  final String text;
  final BadgeTone tone;
  const AppBadge(this.text, {super.key, this.tone = BadgeTone.neutral});

  @override
  Widget build(BuildContext context) {
    final AppColors c = AppColors.of(context);
    final ColorScheme cs = Theme.of(context).colorScheme;
    final Color fg;
    final Color bg;
    switch (tone) {
      case BadgeTone.primary:
        fg = cs.primary;
        bg = cs.primary.withOpacity(0.14);
      case BadgeTone.good:
        fg = c.good;
        bg = c.goodSoft;
      case BadgeTone.bad:
        fg = c.bad;
        bg = c.badSoft;
      case BadgeTone.warn:
        fg = c.warn;
        bg = c.warnSoft;
      case BadgeTone.info:
        fg = c.info;
        bg = c.infoSoft;
      case BadgeTone.neutral:
        fg = cs.onSurfaceVariant;
        bg = cs.onSurface.withOpacity(0.08);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Text(text,
          style: TextStyle(
              fontSize: 11, color: fg, fontWeight: FontWeight.w600, height: 1.3)),
    );
  }
}
