import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show ScheduleItem;
import '../../nav.dart';

class ScheduleNavigation extends StatefulWidget {
  final List<ScheduleItem> items;
  final int index;
  const ScheduleNavigation({super.key, required this.items, required this.index});

  @override
  State<ScheduleNavigation> createState() => _ScheduleNavigationState();
}

class _ScheduleNavigationState extends State<ScheduleNavigation> {
  late List<ScheduleItem> _items = widget.items;

  @override
  void initState() {
    super.initState();
    Api.studyRevision.addListener(_refresh);
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final data = await Endpoints.scheduleToday();
      if (mounted && data.items.any((ScheduleItem item) => item.id == widget.items[widget.index].id)) {
        setState(() => _items = data.items);
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    Api.studyRevision.removeListener(_refresh);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final int index = _items.indexWhere((ScheduleItem item) => item.id == widget.items[widget.index].id);
    int next = -1;
    for (int i = index + 1; index >= 0 && i < _items.length; i++) {
      if (!_items[i].done) { next = i; break; }
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(children: <Widget>[
        TextButton(onPressed: index > 0 ? () => openScheduleItem(context, _items, index - 1, replace: true) : null,
          child: const Text('上一项日程')),
        Expanded(child: Text('日程 ${index + 1} / ${_items.length}', textAlign: TextAlign.center)),
        TextButton(onPressed: next >= 0 ? () => openScheduleItem(context, _items, next, replace: true)
          : () => Navigator.of(context).maybePop(), child: Text(next >= 0 ? '下一项日程' : '返回日程')),
      ]),
    );
  }
}
