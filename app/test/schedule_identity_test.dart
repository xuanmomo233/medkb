import 'package:flutter_test/flutter_test.dart';
import '../lib/models.dart';

void main() {
  test('historical schedule row matches merged identity and preserves its navigation position', () {
    final List<ScheduleItem> items = <ScheduleItem>[
      ScheduleItem.fromJson(<String, dynamic>{'id': 10, 'source_ids': <int>[10], 'done': true}),
      ScheduleItem.fromJson(<String, dynamic>{'id': 20, 'source_ids': <int>[20, 22, 25], 'done': true}),
      ScheduleItem.fromJson(<String, dynamic>{'id': 30, 'source_ids': <int>[30], 'done': false}),
    ];
    final int current = items.indexWhere((ScheduleItem item) => item.matchesId(25));
    expect(current, 1);
    expect(items[current].done, isTrue);
    expect(items.skip(current + 1).firstWhere((ScheduleItem item) => !item.done).id, 30);
    expect(items[current - 1].id, 10);
    expect(items.indexWhere((ScheduleItem item) => item.matchesId(999)), -1);
  });

  test('legacy backend response still matches the original row ID', () {
    final ScheduleItem legacy = ScheduleItem.fromJson(<String, dynamic>{'id': 22});
    expect(legacy.sourceIds, isEmpty);
    expect(legacy.matchesId(22), isTrue);
    expect(legacy.matchesId(25), isFalse);
  });
}
