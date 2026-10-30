import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../lib/models.dart' hide Card;
import '../lib/pages/today/schedule_run_page.dart';
import '../lib/pages/quiz/quiz_run_page.dart';
import '../lib/pages/quiz/option_tile.dart';

void main() {
  testWidgets(
      'small-screen schedule supports multi submit and sequential completed items',
      (tester) async {
    tester.view.physicalSize = const Size(320, 740);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final rows = List.generate(
        2,
        (i) => <String, dynamic>{
              'id': i + 1,
              'item_id': i + 10,
              'item_type': 'question',
              'title': '任务$i',
              'reason': 'due',
              'done': i == 1,
            });
    final attempts = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await tester.pumpWidget(RepaintBoundary(
          key: const ValueKey('screen'),
          child: MaterialApp(
              home: ScheduleRunPage(
            initialIndex: 0,
            day: '2026-10-22',
            items: rows.map(ScheduleItem.fromJson).toList(),
          ))));
      await tester.pumpAndSettle();
      expect(find.text('提交答案').hitTestable(), findsOneWidget);
      expect(find.text('上一题').hitTestable(), findsOneWidget);
      await tester.tap(find.byType(OptionTile).hitTestable().at(0));
      await tester.pump();
      await tester.tap(find.byType(OptionTile).hitTestable().at(2));
      await tester.pump();
      expect(attempts, isEmpty);
      await tester.tap(find.text('提交答案').hitTestable());
      await tester.pumpAndSettle();
      expect(attempts.single['picked'], [0, 2]);
      expect(find.text('下一题').hitTestable(), findsOneWidget);
      await tester.tap(find.text('下一题').hitTestable());
      await tester.pumpAndSettle();
      expect(
          tester
              .widget<QuizRunPage>(find.byType(QuizRunPage).hitTestable())
              .args
              .ids,
          [11]);
      expect(find.text('返回今日').hitTestable(), findsOneWidget);
      await tester.tap(find.text('上一题').hitTestable());
      await tester.pumpAndSettle();
      expect(
          tester
              .widget<QuizRunPage>(find.byType(QuizRunPage).hitTestable())
              .args
              .ids,
          [10]);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
        () => MockClient((request) async {
              Object data;
              if (request.url.path.endsWith('/attempts')) {
                attempts.add(jsonDecode(request.body) as Map<String, dynamic>);
                data = {'correct': true, 'answer': 'AC', 'stat': {}};
              } else if (request.url.path.contains('schedule')) {
                data = {'day': '2026-10-22', 'items': rows, 'done_count': 1};
              } else {
                final id =
                    int.tryParse(request.url.queryParameters['ids'] ?? '') ??
                        10;
                final q = {
                  'id': id,
                  'qid': 'Q$id',
                  'stem_html': '题干$id',
                  'qtype': '多选',
                  'options_html': ['甲', '乙', '丙'],
                  'option_labels': ['A', 'B', 'C'],
                  'answer': 'Ａ、Ｃ',
                  'stat': {}
                };
                data = request.url.path.endsWith('/questions') ? [q] : q;
              }
              return http.Response(jsonEncode(data), 200,
                  headers: {'content-type': 'application/json; charset=utf-8'});
            }));
  });
}
