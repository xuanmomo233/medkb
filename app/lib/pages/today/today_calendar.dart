import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' show CalendarMonth;
import '../../widgets/widgets.dart';
import 'today_common.dart';

class CalendarBlock extends StatefulWidget {
  const CalendarBlock({super.key});

  @override
  State<CalendarBlock> createState() => CalendarBlockState();
}

class CalendarBlockState extends State<CalendarBlock> {
  final GlobalKey<AsyncViewState<CalendarMonth>> _key =
      GlobalKey<AsyncViewState<CalendarMonth>>();
  final DateTime _now = DateTime.now();
  late int _y = _now.year;
  late int _m = _now.month;

  String get _month => '$_y-${_m.toString().padLeft(2, '0')}';

  Future<void> reload() async {
    await _key.currentState?.reload();
  }

  void _shift(int d) {
    final DateTime t = DateTime(_y, _m + d, 1);
    setState(() {
      _y = t.year;
      _m = t.month;
    });
  }

  @override
  Widget build(BuildContext context) {
    return asyncBlock<CalendarMonth>(
      key: _key,
      title: '打卡日历',
      reloadKey: _month,
      loader: () => Endpoints.calendar(_month),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          IconButton(
            tooltip: '上个月',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.chevron_left),
            onPressed: () => _shift(-1),
          ),
          Text('$_y 年 $_m 月',
              style: const TextStyle(fontWeight: FontWeight.w600)),
          IconButton(
            tooltip: '下个月',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.chevron_right),
            onPressed: () => _shift(1),
          ),
        ],
      ),
      builder: (BuildContext ctx, CalendarMonth d, RefreshFn refresh) {
        final bool thisMonth = _y == _now.year && _m == _now.month;
        return _MonthGrid(
          year: _y,
          month: _m,
          days: d.days.toSet(),
          today: thisMonth ? _now.day : -1,
        );
      },
    );
  }
}

class _MonthGrid extends StatelessWidget {
  final int year;
  final int month;
  final Set<int> days;
  final int today;
  const _MonthGrid({
    required this.year,
    required this.month,
    required this.days,
    required this.today,
  });

  static const List<String> _week = <String>['一', '二', '三', '四', '五', '六', '日'];

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final int offset = (DateTime(year, month, 1).weekday + 6) % 7;
    final int total = DateTime(year, month + 1, 0).day;
    final int rows = ((offset + total) / 7).ceil();
    final List<Widget> head = _week
        .map((String w) => Expanded(
              child: Center(
                child: Text(w,
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ),
            ))
        .toList();
    final List<Widget> body = <Widget>[];
    for (int r = 0; r < rows; r++) {
      final List<Widget> cells = <Widget>[];
      for (int c = 0; c < 7; c++) {
        final int day = r * 7 + c - offset + 1;
        if (day < 1 || day > total) {
          cells.add(const Expanded(child: SizedBox(height: 40)));
        } else {
          cells.add(Expanded(
            child: _DayCell(
                day: day, on: days.contains(day), isToday: day == today),
          ));
        }
      }
      body.add(Row(children: cells));
    }
    return Column(
      children: <Widget>[
        Row(children: head),
        const SizedBox(height: 4),
        ...body,
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final int day;
  final bool on;
  final bool isToday;
  const _DayCell({required this.day, required this.on, required this.isToday});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return SizedBox(
      height: 40,
      child: Center(
        child: Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: on ? cs.primary : null,
            border: isToday ? Border.all(color: cs.primary, width: 1.5) : null,
          ),
          child: Text(
            '$day',
            style: TextStyle(
              fontSize: 13,
              fontWeight: on || isToday ? FontWeight.w700 : FontWeight.w400,
              color: on ? cs.onPrimary : cs.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}
