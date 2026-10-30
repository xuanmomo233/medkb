import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/models.dart' hide Card;
import '../lib/pages/today/today_schedule.dart';

void main() {
  testWidgets(
      'pending tasks precede collapsed completed tasks on a narrow screen',
      (tester) async {
    tester.view.physicalSize = const Size(320, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
      child: ScheduleList(
          data: ScheduleToday(
              day: '2026-10-22',
              goal: 12,
              doneCount: 6,
              items: List.generate(
                  12,
                  (i) => ScheduleItem(
                      id: i,
                      itemType: 'question',
                      itemId: i,
                      reason: 'due',
                      title: '长题干任务$i：此处用于验证小屏标题与复习标签的排版',
                      done: i < 6))),
          onReturn: () {},
          onChanged: () {}),
    ))));
    expect(find.textContaining('长题干任务0：'), findsNothing);
    expect(find.textContaining('长题干任务6：'), findsOneWidget);
    expect(find.textContaining('长题干任务11：'), findsNothing);
    await tester.tap(find.text('展开全部任务'));
    await tester.pumpAndSettle();
    expect(find.textContaining('长题干任务11：'), findsOneWidget);
    await tester.ensureVisible(find.text('查看已完成（6）'));
    await tester.tap(find.text('查看已完成（6）'));
    await tester.pumpAndSettle();
    expect(find.textContaining('长题干任务0：'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
