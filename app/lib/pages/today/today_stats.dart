import 'package:flutter/material.dart';
import '../../models.dart' show DailyStat, QuizFilter, StatsOverview, SystemStat, WeakSpot;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import '../me/settings_page.dart';
import 'today_common.dart';

String _ago(String? iso) {
  if (iso == null || iso.isEmpty) return '未作答';
  final DateTime? t = DateTime.tryParse(iso);
  if (t == null) return '未知';
  final int days = DateTime.now().difference(t).inDays;
  return days <= 0 ? '今天' : '$days 天前';
}

class WeakList extends StatelessWidget {
  final List<WeakSpot> list;
  final VoidCallback onReturn;
  const WeakList({super.key, required this.list, required this.onReturn});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    if (list.isEmpty) {
      return EmptyState(
        '继续刷题，累计样本后将自动分析薄弱点',
        icon: Icons.track_changes_outlined,
        action: TextButton(
          onPressed: () => Navigator.of(context)
              .push<void>(MaterialPageRoute<void>(
                  builder: (_) => const SettingsPage()))
              .then((_) => onReturn()),
          child: const Text('调整阈值'),
        ),
      );
    }
    final List<WeakSpot> sorted = List<WeakSpot>.of(list)
      ..sort((WeakSpot a, WeakSpot b) => a.rate.compareTo(b.rate));
    return Column(
      children: sorted.map((WeakSpot w) {
        final Color col = rateColor(context, w.rate);
        return InkWell(
          onTap: () => openQuizRun(
            context,
            QuizRunArgs(
              filter: QuizFilter(system: w.system, chapter: w.chapter),
              title: '${w.system} · ${w.chapter}',
            ),
          ).then((_) => onReturn()),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text('${w.system} · ${w.chapter}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                    ),
                    Text('${pct(w.rate)}%',
                        style: TextStyle(
                            fontWeight: FontWeight.w800, color: col)),
                  ],
                ),
                const SizedBox(height: 6),
                ProgressBar(value: w.rate, color: col),
                const SizedBox(height: 4),
                Text('做题 ${w.total} · 最近作答 ${_ago(w.lastAttemptAt)}',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class StatsBody extends StatelessWidget {
  final StatsOverview data;
  const StatsBody({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool noDaily = data.daily.every((DailyStat x) => x.count == 0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(child: _stat(context, '${data.attempted}', '已做题')),
            Expanded(
                child: _stat(context, '${pct(data.accuracy)}%', '总正确率')),
          ],
        ),
        const SizedBox(height: 14),
        Text('近 30 天做题量',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
        const SizedBox(height: 8),
        if (noDaily)
          const SizedBox(
              height: 100,
              child: EmptyState('近 30 天暂无做题记录', icon: Icons.bar_chart_outlined))
        else
          SizedBox(
            height: 110,
            child: CustomPaint(
              size: Size.infinite,
              painter: _BarsPainter(
                data.daily,
                cs.primary,
                cs.onSurface.withOpacity(0.08),
              ),
            ),
          ),
        const SizedBox(height: 14),
        Text('各系统正确率',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
        const SizedBox(height: 6),
        if (data.bySystem.isEmpty)
          const SizedBox(
              height: 80, child: EmptyState('暂无系统统计', icon: Icons.pie_chart_outline))
        else
          ...data.bySystem.map((SystemStat x) {
            final Color col = rateColor(context, x.rate);
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: <Widget>[
                  SizedBox(
                    width: 84,
                    child: Text(x.system,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 13)),
                  ),
                  Expanded(child: ProgressBar(value: x.rate, color: col)),
                  SizedBox(
                    width: 46,
                    child: Text('${pct(x.rate)}%',
                        textAlign: TextAlign.right,
                        style: TextStyle(
                            fontWeight: FontWeight.w700, color: col)),
                  ),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget _stat(BuildContext context, String v, String label) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        BigNumber(v, size: 30),
        const SizedBox(height: 2),
        Text(label,
            style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant)),
      ],
    );
  }
}

class _BarsPainter extends CustomPainter {
  final List<DailyStat> data;
  final Color color;
  final Color track;
  _BarsPainter(this.data, this.color, this.track);

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;
    int maxV = 1;
    for (final DailyStat d in data) {
      if (d.count > maxV) maxV = d.count;
    }
    final double slot = size.width / data.length;
    final double bw = slot * 0.62;
    final Paint base = Paint()..color = track;
    final Paint bar = Paint()..color = color;
    for (int i = 0; i < data.length; i++) {
      final double x = i * slot + (slot - bw) / 2;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(x, size.height - 2, bw, 2), const Radius.circular(1)),
        base,
      );
      final int c = data[i].count;
      if (c <= 0) continue;
      final double h = (size.height - 2) * c / maxV;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(x, size.height - 2 - h, bw, h), const Radius.circular(2)),
        bar,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _BarsPainter old) =>
      old.data != data || old.color != color || old.track != track;
}
