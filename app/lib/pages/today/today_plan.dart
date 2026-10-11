import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart'
    show PlanDayCard, PlanDayDetail, PlanOverviewDay, PlanQuestionGroup, PlanToday;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import '../notes/note_time.dart';
import 'today_common.dart';

double _ratio(int a, int b) => b > 0 ? a / b : 0.0;

class PlanBody extends StatefulWidget {
  final PlanToday plan;
  final VoidCallback onReturn;
  final VoidCallback onRestarted;
  const PlanBody({
    super.key,
    required this.plan,
    required this.onReturn,
    required this.onRestarted,
  });

  @override
  State<PlanBody> createState() => _PlanBodyState();
}

class _PlanBodyState extends State<PlanBody> {
  int? _open;
  bool _busy = false;

  Future<void> _restart() async {
    final bool ok = await confirmDialog(
        context, '重新开始计划', '将从第 1 天重新开始，当前计划进度会被清空。确定继续吗？',
        okText: '确认重新开始');
    if (!ok || !mounted) return;
    setState(() => _busy = true);
    try {
      await Endpoints.planRestart();
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, '计划已重新开始');
      widget.onRestarted();
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, errText(e));
    }
  }

  void _go(Future<void> f) {
    f.then((_) => widget.onReturn());
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final PlanToday p = widget.plan;
    if (p.totalDays == 0 && p.overview.isEmpty) {
      return const SizedBox(
          height: 100, child: EmptyState('暂无学习计划', icon: Icons.map_outlined));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        if (p.finished)
          EmptyState(
            '${p.totalDays} 天计划已全部完成，太棒了！',
            icon: Icons.celebration_outlined,
            action: FilledButton(
              onPressed: _busy ? null : _restart,
              child: const Text('重新开始计划'),
            ),
          )
        else ...<Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Text('第 ', style: TextStyle(color: cs.onSurfaceVariant)),
              BigNumber('${p.todayNo}'),
              Text(' / ${p.totalDays} 天',
                  style: TextStyle(color: cs.onSurfaceVariant)),
              const SizedBox(width: 10),
              Expanded(
                child: Align(
                  alignment: Alignment.centerRight,
                  child: Text(p.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          color: cs.primary, fontWeight: FontWeight.w600)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _progress('卡片', p.cardDone, p.cardIds.length),
          const SizedBox(height: 8),
          _progress('题目', p.questionDone, p.questionIds.length),
          const SizedBox(height: 12),
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton(
                  onPressed: () =>
                      _go(openCardRun(context, CardRunArgs(planDay: p.todayNo))),
                  child: const Text('开始背卡'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.tonal(
                  onPressed: () =>
                      _go(openQuizRun(context, QuizRunArgs(planDay: p.todayNo))),
                  child: const Text('开始刷题'),
                ),
              ),
              const SizedBox(width: 4),
              TextButton(
                onPressed: _busy ? null : _restart,
                child: const Text('重新开始'),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        const Divider(height: 1),
        ...p.overview.map((PlanOverviewDay d) => _dayRow(context, p, d)),
      ],
    );
  }

  Widget _progress(String label, int done, int total) {
    return Column(
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(label,
                style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant)),
            const Spacer(),
            Text('$done / $total',
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        const SizedBox(height: 4),
        ProgressBar(value: _ratio(done, total)),
      ],
    );
  }

  Widget _dayRow(BuildContext context, PlanToday p, PlanOverviewDay d) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool open = _open == d.no;
    final bool now = d.no == p.todayNo && !p.finished;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        InkWell(
          onTap: () => setState(() => _open = open ? null : d.no),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Row(
              children: <Widget>[
                SizedBox(
                  width: 40,
                  child: Text('D${d.no}',
                      style: TextStyle(
                          fontWeight: FontWeight.w800,
                          color: now ? cs.primary : cs.onSurfaceVariant)),
                ),
                Expanded(
                  child: Text(d.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontWeight: now ? FontWeight.w700 : FontWeight.w400)),
                ),
                Text('${d.cardCount} 卡',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                Icon(open ? Icons.expand_less : Icons.expand_more,
                    color: cs.onSurfaceVariant),
              ],
            ),
          ),
        ),
        if (open) _PlanDayDetailView(no: d.no, onGo: _go),
        const Divider(height: 1),
      ],
    );
  }
}

class _PlanDayDetailView extends StatelessWidget {
  final int no;
  final void Function(Future<void> f) onGo;
  const _PlanDayDetailView({required this.no, required this.onGo});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: cs.onSurface.withOpacity(0.04),
        borderRadius: BorderRadius.circular(10),
      ),
      child: AsyncView<PlanDayDetail>(
        key: ValueKey<int>(no),
        loader: () => Endpoints.planDay(no),
        showCacheBanner: false,
        builder: (BuildContext ctx, PlanDayDetail d, RefreshFn refresh) {
          if (d.cards.isEmpty && d.questionGroups.isEmpty) {
            return Text('这一天没有内容',
                style: TextStyle(color: cs.onSurfaceVariant));
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if (d.cards.isNotEmpty) ...<Widget>[
                Text('卡片 ${d.cards.length} 张',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: d.cards
                      .map((PlanDayCard c) => ActionChip(
                            label: Text(c.term),
                            visualDensity: VisualDensity.compact,
                            onPressed: () => onGo(openCardRun(
                                context, CardRunArgs(ids: <int>[c.id]))),
                          ))
                      .toList(),
                ),
              ],
              if (d.questionGroups.isNotEmpty) ...<Widget>[
                const SizedBox(height: 10),
                Text('题目',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                ...d.questionGroups.map((PlanQuestionGroup g) => InkWell(
                      onTap: () => onGo(openQuizRun(
                          context, QuizRunArgs(ids: g.ids, title: g.chapter))),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(minHeight: 44),
                        child: Row(
                          children: <Widget>[
                            Expanded(child: Text(g.chapter)),
                            Text('${g.ids.length} 题',
                                style: TextStyle(
                                    fontSize: 12, color: cs.onSurfaceVariant)),
                            const Icon(Icons.chevron_right, size: 18),
                          ],
                        ),
                      ),
                    )),
              ],
            ],
          );
        },
      ),
    );
  }
}
