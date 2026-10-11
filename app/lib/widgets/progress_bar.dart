import 'package:flutter/material.dart';

/// 细进度条，value 取 0~1
class ProgressBar extends StatelessWidget {
  final double value;
  final double height;
  final Color? color;
  const ProgressBar({super.key, required this.value, this.height = 6, this.color});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final double v = value.isNaN ? 0.0 : value.clamp(0.0, 1.0).toDouble();
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: LinearProgressIndicator(
        value: v,
        minHeight: height,
        color: color ?? cs.primary,
        backgroundColor: cs.onSurface.withOpacity(0.08),
      ),
    );
  }
}
