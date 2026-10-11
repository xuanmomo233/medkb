import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show TodayCounts, TodaySummary;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';
import '../me/settings_page.dart';
import 'today_common.dart';

String greeting() {
  final int h = DateTime.now().hour;
  if (h < 6) return '夜深了';
  if (h < 12) return '早上好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

class GreetingBlock extends StatelessWidget {
  final TodaySummary data;
  final VoidCallback onReturn;
  const GreetingBlock({super.key, required this.data, required this.onReturn});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final int? left = data.examDaysLeft;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(greeting(),
                  style: Theme.of(context)
                      .textTheme
                      .headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text('保持节奏，今天也向目标靠近一步',
                  style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant)),
            ],
          ),
        ),
        const SizedBox(width: 12),
        InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: left == null
              ? () => Navigator.of(context)
                  .push<void>(MaterialPageRoute<void>(
                      builder: (_) => const SettingsPage()))
                  .then((_) => onReturn())
              : null,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Center(
              child: left == null
                  ? Text('设置考研日期\n开启倒计时 ›',
                      textAlign: TextAlign.right,
                      style: TextStyle(fontSize: 12, color: cs.primary))
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: <Widget>[
                        Text('距考研还有',
                            style: TextStyle(
                                fontSize: 11, color: cs.onSurfaceVariant)),
                        BigNumber('$left', unit: '天', color: cs.primary),
                      ],
                    ),
            ),
          ),
        ),
      ],
    );
  }
}

class CheckinBlock extends StatefulWidget {
  final TodaySummary data;
  final VoidCallback onChecked;
  const CheckinBlock({super.key, required this.data, required this.onChecked});

  @override
  State<CheckinBlock> createState() => _CheckinBlockState();
}

class _CheckinBlockState extends State<CheckinBlock> {
  bool _busy = false;

  Future<void> _checkin() async {
    setState(() => _busy = true);
    try {
      final int streak = await Endpoints.checkin();
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, '打卡成功，已连续 $streak 天');
      widget.onChecked();
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, errText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final TodaySummary d = widget.data;
    final double ratio = d.dailyGoal > 0 ? d.doneToday / d.dailyGoal : 0;
    final bool reached = d.dailyGoal > 0 && d.doneToday >= d.dailyGoal;
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('连续打卡',
                      style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                  const SizedBox(height: 2),
                  BigNumber('${d.streak}', unit: '天', size: 36),
                ],
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: (d.checkedIn || _busy) ? null : _checkin,
                icon: Icon(d.checkedIn ? Icons.check : Icons.flag_outlined, size: 18),
                label: Text(d.checkedIn ? '今日已打卡' : (_busy ? '打卡中…' : '打卡')),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: <Widget>[
              Text('今日目标',
                  style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              const Spacer(),
              Text('${d.doneToday} / ${d.dailyGoal}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 6),
          ProgressBar(
              value: ratio, height: 8, color: reached ? AppColors.of(context).good : null),
        ],
      ),
    );
  }
}

class TodoBlock extends StatelessWidget {
  final TodayCounts counts;
  final VoidCallback onReturn;
  const TodoBlock({super.key, required this.counts, required this.onReturn});

  void _go(BuildContext context, Future<void> f) {
    f.then((_) => onReturn());
  }

  @override
  Widget build(BuildContext context) {
    final AppColors c = AppColors.of(context);
    return BlockCard(
      title: '待办入口',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              _tile(context, '到期题', counts.due, c.info, c.infoSoft,
                  () => _go(context, openQuizRun(context, const QuizRunArgs(due: true)))),
              const SizedBox(width: 8),
              _tile(context, '错题', counts.wrong, c.bad, c.badSoft,
                  () => _go(context, openQuizRun(context, const QuizRunArgs(wrong: true)))),
              const SizedBox(width: 8),
              _tile(context, '收藏题', counts.starred, c.warn, c.warnSoft,
                  () => _go(context, openQuizRun(context, const QuizRunArgs(starred: true)))),
              const SizedBox(width: 8),
              _tile(context, '已掌握', counts.mastered, c.good, c.goodSoft, null),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: <Widget>[
              Text('背卡',
                  style: TextStyle(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurfaceVariant)),
              const SizedBox(width: 12),
              ActionChip(
                label: const Text('到期背卡'),
                onPressed: () =>
                    _go(context, openCardRun(context, const CardRunArgs(due: true))),
              ),
              const SizedBox(width: 8),
              ActionChip(
                label: const Text('收藏卡'),
                onPressed: () => _go(
                    context, openCardRun(context, const CardRunArgs(starred: true))),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _tile(BuildContext context, String label, int n, Color fg, Color bg,
      VoidCallback? onTap) {
    return Expanded(
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Column(
              children: <Widget>[
                Text('$n',
                    style: TextStyle(
                        fontSize: 22, fontWeight: FontWeight.w800, color: fg)),
                const SizedBox(height: 2),
                Text(label, style: TextStyle(fontSize: 12, color: fg)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
