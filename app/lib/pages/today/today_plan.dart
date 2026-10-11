import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart'
    show PlanDayCard, PlanDayDetail, PlanItem, PlanOption, PlanQuestionGroup, PlanToday;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import '../notes/note_time.dart' show confirmDialog;
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
        context, '重新开始计划', '剩余内容将从今天起重新均分到剩余天数里。确定继续吗？',
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

  Future<void> _edit() async {
    final bool saved =
        await PlanSetupSheet.show(context) ?? false;
    if (saved && mounted) widget.onRestarted();
  }

  void _go(Future<void> f) {
    f.then((_) => widget.onReturn());
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final PlanToday p = widget.plan;
    if (!p.configured) {
      return SizedBox(
        height: 140,
        child: EmptyState('还没有学习计划，自己选内容定天数',
            icon: Icons.map_outlined,
            action: FilledButton.icon(
              onPressed: _edit,
              icon: const Icon(Icons.tune, size: 18),
              label: const Text('设置学习计划'),
            )),
      );
    }
    final List<int> days = p.items
        .where((PlanItem i) => i.day != null)
        .map((PlanItem i) => i.day!)
        .toSet()
        .toList()
      ..sort();
    final int todayCards =
        p.todayItems.fold(0, (int n, PlanItem i) => n + i.cards);
    final int todayQ =
        p.todayItems.fold(0, (int n, PlanItem i) => n + i.questions);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        if (p.finished)
          EmptyState(
            '${p.totalDays} 天计划已全部完成，太棒了！',
            icon: Icons.celebration_outlined,
            action: FilledButton(
              onPressed: _edit,
              child: const Text('设置新计划'),
            ),
          )
        else ...<Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Text('第 ', style: TextStyle(color: cs.onSurfaceVariant)),
              BigNumber('${p.dayNo}'),
              Text(' / ${p.totalDays} 天 · 剩 ${p.daysLeft} 天 · 还有 ${p.remaining} 章',
                  style: TextStyle(color: cs.onSurfaceVariant)),
            ],
          ),
          const SizedBox(height: 12),
          if (p.todayItems.isEmpty)
            Text('今天没有安排，剩余内容已排进后面的天数',
                style: TextStyle(color: cs.onSurfaceVariant))
          else
            ...p.todayItems.map(_itemRow),
          const SizedBox(height: 12),
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton(
                  onPressed: p.todayItems.isEmpty
                      ? null
                      : () => _go(
                          openCardRun(context, const CardRunArgs(planDay: 1))),
                  child: Text('背卡 $todayCards'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.tonal(
                  onPressed: p.todayItems.isEmpty
                      ? null
                      : () => _go(
                          openQuizRun(context, const QuizRunArgs(planDay: 1))),
                  child: Text('刷题 $todayQ'),
                ),
              ),
            ],
          ),
          Row(
            children: <Widget>[
              TextButton.icon(
                  onPressed: _edit,
                  icon: const Icon(Icons.tune, size: 16),
                  label: const Text('修改计划')),
              const Spacer(),
              TextButton(onPressed: _busy ? null : _restart, child: const Text('重新开始')),
            ],
          ),
        ],
        if (days.isNotEmpty) ...<Widget>[
          const Divider(height: 1),
          ...days.map((int d) => _dayRow(context, p, d)),
        ],
      ],
    );
  }

  Widget _itemRow(PlanItem it) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final double pct = _ratio(it.cardDone + it.questionDone, it.cards + it.questions);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(it.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              Text('${it.cardDone}/${it.cards}卡 · ${it.questionDone}/${it.questions}题',
                  style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
            ],
          ),
          const SizedBox(height: 4),
          ProgressBar(value: pct),
        ],
      ),
    );
  }

  Widget _dayRow(BuildContext context, PlanToday p, int day) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool open = _open == day;
    final List<PlanItem> items =
        p.items.where((PlanItem i) => i.day == day).toList();
    final String title = items.map((PlanItem i) => i.part).join('、');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        InkWell(
          onTap: () => setState(() => _open = open ? null : day),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Row(
              children: <Widget>[
                SizedBox(
                  width: 40,
                  child: Text(day == 1 ? '今' : 'D$day',
                      style: TextStyle(
                          fontWeight: FontWeight.w800,
                          color: day == 1 ? cs.primary : cs.onSurfaceVariant)),
                ),
                Expanded(
                  child: Text(title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontWeight:
                              day == 1 ? FontWeight.w700 : FontWeight.w400)),
                ),
                Text('${items.length} 章',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                Icon(open ? Icons.expand_less : Icons.expand_more,
                    color: cs.onSurfaceVariant),
              ],
            ),
          ),
        ),
        if (open) _PlanDayDetailView(no: day, onGo: _go),
        const Divider(height: 1),
      ],
    );
  }
}

/// 设置计划：选章（subject+part）+ 完成天数
class PlanSetupSheet extends StatefulWidget {
  const PlanSetupSheet({super.key});

  static Future<bool?> show(BuildContext context) => showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (BuildContext ctx) => const PlanSetupSheet(),
      );

  @override
  State<PlanSetupSheet> createState() => _PlanSetupSheetState();
}

class _PlanSetupSheetState extends State<PlanSetupSheet> {
  final Set<String> _picked = <String>{};
  int _days = 10;
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
          left: 16,
          right: 16),
      child: ConstrainedBox(
        constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text('设置学习计划',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text('勾选要学的章节，设定完成天数；当天没完成的自动顺延并重新均分',
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
            const SizedBox(height: 8),
            Expanded(
              child: AsyncView<List<PlanOption>>(
                loader: Endpoints.planOptions,
                showCacheBanner: false,
                builder: (BuildContext ctx, List<PlanOption> opts, RefreshFn r) {
                  return ListView(
                    children: opts.map((PlanOption g) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(g.subject,
                                style: TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: cs.primary,
                                    fontSize: 13)),
                            const SizedBox(height: 6),
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: g.parts.map((p) {
                                final String k = '${g.subject}|${p.part}';
                                final bool on = _picked.contains(k);
                                return FilterChip(
                                  label: Text(
                                      '${p.part} ${p.cards}卡·${p.questions}题'),
                                  selected: on,
                                  visualDensity: VisualDensity.compact,
                                  onSelected: (_) => setState(() =>
                                      on ? _picked.remove(k) : _picked.add(k)),
                                );
                              }).toList(),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  );
                },
              ),
            ),
            const Divider(height: 16),
            Row(
              children: <Widget>[
                Text('完成天数', style: TextStyle(color: cs.onSurfaceVariant)),
                IconButton(
                    onPressed: _days > 1
                        ? () => setState(() => _days -= 1)
                        : null,
                    icon: const Icon(Icons.remove_circle_outline, size: 20)),
                Text('$_days 天',
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                IconButton(
                    onPressed: _days < 120
                        ? () => setState(() => _days += 1)
                        : null,
                    icon: const Icon(Icons.add_circle_outline, size: 20)),
                const Spacer(),
                Text('已选 ${_picked.length} 章',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _picked.isEmpty || _busy ? null : _save,
                  child: Text(_busy ? '保存中…' : '保存计划'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      final List<Map<String, String>> items = _picked
          .map((String k) {
            final int i = k.indexOf('|');
            return <String, String>{
              'subject': k.substring(0, i),
              'part': k.substring(i + 1),
            };
          })
          .toList();
      await Endpoints.planSaveConfig(_days, items);
      if (!mounted) return;
      toast(context, '学习计划已保存，从今天开始');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, errText(e));
    }
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
