import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show ScheduleItem, ScheduleToday, TargetType;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'today_common.dart';

class ScheduleList extends StatefulWidget {
  final ScheduleToday data;
  final VoidCallback onReturn;
  final VoidCallback onChanged;
  const ScheduleList({
    super.key,
    required this.data,
    required this.onReturn,
    required this.onChanged,
  });

  @override
  State<ScheduleList> createState() => ScheduleListState();
}

class ScheduleListState extends State<ScheduleList> {
  late List<ScheduleItem> _items = List<ScheduleItem>.of(widget.data.items);
  final Set<int> _pending = <int>{};

  @override
  void didUpdateWidget(covariant ScheduleList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.data, widget.data)) {
      _items = List<ScheduleItem>.of(widget.data.items);
    }
  }

  ScheduleItem _withDone(ScheduleItem x, bool done) => ScheduleItem(
        id: x.id,
        itemType: x.itemType,
        itemId: x.itemId,
        reason: x.reason,
        title: x.title,
        done: done,
      );

  void _setDone(int id, bool done) {
    setState(() {
      _items = _items
          .map((ScheduleItem x) => x.id == id ? _withDone(x, done) : x)
          .toList();
    });
  }

  Future<void> _complete(ScheduleItem it) async {
    if (it.done || _pending.contains(it.id)) return;
    _pending.add(it.id);
    _setDone(it.id, true);
    try {
      await Endpoints.scheduleDone(it.id);
      if (!mounted) return;
      widget.onChanged();
    } catch (e) {
      if (!mounted) return;
      _setDone(it.id, false);
      toast(context, errText(e));
    } finally {
      _pending.remove(it.id);
    }
  }

  void _open(ScheduleItem it) {
    final Future<void> f = it.itemType == TargetType.question
        ? openQuizRun(context, QuizRunArgs(ids: <int>[it.itemId]))
        : openCardRun(context, CardRunArgs(ids: <int>[it.itemId]));
    f.then((_) => widget.onReturn());
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final int done = _items.where((ScheduleItem x) => x.done).length;
    if (_items.isEmpty) {
      return const SizedBox(
          height: 120, child: EmptyState('今天暂无日程，去刷几道题吧', icon: Icons.event_available_outlined));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: ProgressBar(value: done / _items.length),
            ),
            const SizedBox(width: 10),
            Text('$done / ${_items.length}',
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        const SizedBox(height: 4),
        ..._items.map((ScheduleItem it) {
          final bool isQ = it.itemType == TargetType.question;
          final bool due = it.reason == 'due';
          return InkWell(
            onTap: () => _open(it),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48),
              child: Row(
                children: <Widget>[
                  Checkbox(
                    value: it.done,
                    onChanged: it.done ? null : (bool? _) => _complete(it),
                  ),
                  Icon(isQ ? Icons.edit_note : Icons.style_outlined,
                      size: 18, color: cs.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      it.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        decoration:
                            it.done ? TextDecoration.lineThrough : null,
                        color: it.done ? cs.onSurfaceVariant : null,
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  AppBadge(due ? '到期复习' : '薄弱补强',
                      tone: due ? BadgeTone.info : BadgeTone.warn),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }
}
