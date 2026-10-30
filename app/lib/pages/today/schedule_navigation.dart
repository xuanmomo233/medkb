import 'package:flutter/material.dart';
import '../../models.dart' show ScheduleItem, TargetType;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';
import 'schedule_session.dart';

Future<void> showScheduleJump(
    BuildContext context, ScheduleSession session) async {
  final selected = await showAppSheet<int>(context,
      title: '题号跳转',
      builder: (ctx) => AnimatedBuilder(
          animation: session,
          builder: (ctx, _) {
            final cs = Theme.of(ctx).colorScheme;
            final colors = AppColors.of(ctx);
            return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                      child: Text('共 ${session.items.length} 项 · 可直接跳转，保留作答状态',
                          style: TextStyle(color: cs.onSurfaceVariant))),
                  Flexible(
                      child: GridView.builder(
                    shrinkWrap: true,
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                    gridDelegate:
                        const SliverGridDelegateWithMaxCrossAxisExtent(
                            maxCrossAxisExtent: 86,
                            mainAxisSpacing: 8,
                            crossAxisSpacing: 8),
                    itemCount: session.items.length,
                    itemBuilder: (ctx, index) {
                      final item = session.items[index];
                      final answer = item.itemType == TargetType.question
                          ? session.savedAnswer(item.itemId)
                          : null;
                      final judged = answer?['judged'] == true;
                      final picked = answer?['picked'];
                      final draft = picked is String && picked.isNotEmpty;
                      final rated = item.itemType == TargetType.card &&
                          session.ratings.containsKey(item.itemId);
                      final current = session.index == index;
                      final bg = judged
                          ? (answer?['correct'] == true
                              ? colors.goodSoft
                              : colors.badSoft)
                          : item.done || rated
                              ? colors.goodSoft
                              : draft
                                  ? colors.infoSoft
                                  : cs.surfaceContainerHighest;
                      return Semantics(
                          label: '第 ${index + 1} 题，${item.title}',
                          selected: current,
                          child: Tooltip(
                              message: item.title,
                              child: InkWell(
                                borderRadius: BorderRadius.circular(10),
                                onTap: () => Navigator.of(ctx).pop(index),
                                child: Container(
                                    decoration: BoxDecoration(
                                        color: bg,
                                        borderRadius: BorderRadius.circular(10),
                                        border: Border.all(
                                            color: current
                                                ? cs.primary
                                                : cs.outlineVariant,
                                            width: current ? 2 : 1)),
                                    child: Stack(children: [
                                      Center(
                                          child: Column(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                            Text('${index + 1}',
                                                style: const TextStyle(
                                                    fontSize: 18,
                                                    fontWeight:
                                                        FontWeight.w700)),
                                            Text(
                                                item.itemType ==
                                                        TargetType.question
                                                    ? '题目'
                                                    : '卡片',
                                                style: TextStyle(
                                                    fontSize: 11,
                                                    color:
                                                        cs.onSurfaceVariant)),
                                          ])),
                                      if (item.done || judged || rated)
                                        Positioned(
                                            top: 3,
                                            right: 3,
                                            child: Icon(
                                                judged &&
                                                        answer?['correct'] ==
                                                            false
                                                    ? Icons.close
                                                    : Icons.check,
                                                size: 12)),
                                    ])),
                              )));
                    },
                  )),
                ]);
          }));
  if (context.mounted && selected != null) session.go(selected);
}

class ScheduleNavigation extends StatelessWidget {
  final List<ScheduleItem> items;
  final int index;
  final Widget? action;
  final ScheduleSession? session;
  const ScheduleNavigation(
      {super.key,
      required this.items,
      required this.index,
      this.action,
      this.session});

  @override
  Widget build(BuildContext context) {
    if (session != null)
      return AnimatedBuilder(
          animation: session!,
          builder: (ctx, _) => _bar(ctx, session!.items, session!.index));
    return _bar(context, items, index);
  }

  Widget _bar(BuildContext context, List<ScheduleItem> queue, int current) {
    void go(int next) {
      if (session != null) {
        session!.go(next);
      } else {
        openScheduleItem(context, queue, next, replace: true);
      }
    }

    return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(children: [
          TextButton(
              style: TextButton.styleFrom(minimumSize: const Size(64, 48)),
              onPressed: current > 0 ? () => go(current - 1) : null,
              child: const Text('上一题')),
          Expanded(
              child: action ??
                  TextButton.icon(
                      onPressed: session != null ? session!.onOpenJump : null,
                      icon: const Icon(Icons.grid_view, size: 16),
                      label: Text('${current + 1} / ${queue.length}'))),
          TextButton(
              style: TextButton.styleFrom(minimumSize: const Size(64, 48)),
              onPressed: current + 1 < queue.length
                  ? () => go(current + 1)
                  : () => Navigator.of(context).maybePop(),
              child: Text(current + 1 < queue.length ? '下一题' : '返回今日')),
        ]));
  }
}
