import 'package:flutter/material.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';

typedef RefreshFn = Future<void> Function();

int pct(double r) => (r * 100).round();

Color rateColor(BuildContext context, double r) {
  final AppColors c = AppColors.of(context);
  if (r >= 0.75) return c.good;
  if (r >= 0.55) return c.warn;
  return c.bad;
}

class BlockCard extends StatelessWidget {
  final String title;
  final Widget? trailing;
  final Widget child;
  const BlockCard({
    super.key,
    required this.title,
    required this.child,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .titleSmall
                        ?.copyWith(fontWeight: FontWeight.w700)),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

/// 在无界高度容器（ListView）里使用的独立加载块
Widget asyncBlock<T>({
  Key? key,
  required String title,
  Widget? trailing,
  required Future<T> Function() loader,
  required Widget Function(BuildContext context, T data, RefreshFn refresh) builder,
  Object? reloadKey,
}) {
  return BlockCard(
    title: title,
    trailing: trailing,
    child: ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 96),
      child: AsyncView<T>(
        key: key,
        loader: loader,
        reloadKey: reloadKey,
        showCacheBanner: false,
        builder: builder,
      ),
    ),
  );
}

class BigNumber extends StatelessWidget {
  final String value;
  final String? unit;
  final Color? color;
  final double size;
  const BigNumber(this.value, {super.key, this.unit, this.color, this.size = 28});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: <Widget>[
        Text(value,
            style: TextStyle(
                fontSize: size,
                fontWeight: FontWeight.w800,
                color: color,
                height: 1.1)),
        if (unit != null) ...<Widget>[
          const SizedBox(width: 4),
          Text(unit!, style: TextStyle(fontSize: 12, color: grey)),
        ],
      ],
    );
  }
}
