import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import '../../widgets/widgets.dart';

class CardSummary extends StatelessWidget {
  final int total;
  final Map<int, String> ratings;
  final VoidCallback onRestart;
  final VoidCallback onPrev;
  const CardSummary({
    super.key,
    required this.total,
    required this.ratings,
    required this.onRestart,
    required this.onPrev,
  });

  int _count(String a) =>
      ratings.values.where((String v) => v == a).length;

  Widget _stat(BuildContext context, String label, int n, Color fg, Color bg) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration:
            BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
        child: Column(
          children: <Widget>[
            Text('$n',
                style: TextStyle(
                    fontSize: 22, fontWeight: FontWeight.w800, color: fg)),
            Text(label, style: TextStyle(fontSize: 12, color: fg)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppColors c = AppColors.of(context);
    final ColorScheme cs = Theme.of(context).colorScheme;
    final int skipped = total - ratings.length;
    return AppCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: <Widget>[
          Icon(Icons.celebration_outlined, size: 44, color: cs.primary),
          const SizedBox(height: 8),
          Text('本轮完成',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text('共 $total 张${skipped > 0 ? '，其中 $skipped 张未评分' : ''}',
              style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant)),
          const SizedBox(height: 16),
          Row(
            children: <Widget>[
              _stat(context, '忘了', _count(MarkAction.rateAgain), c.bad, c.badSoft),
              const SizedBox(width: 10),
              _stat(context, '模糊', _count(MarkAction.rateHard), c.warn, c.warnSoft),
              const SizedBox(width: 10),
              _stat(context, '记住', _count(MarkAction.rateGood), c.good, c.goodSoft),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
                onPressed: onRestart, child: const Text('再来一轮')),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
                onPressed: onPrev, child: const Text('回看最后一张')),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('返回')),
          ),
        ],
      ),
    );
  }
}
