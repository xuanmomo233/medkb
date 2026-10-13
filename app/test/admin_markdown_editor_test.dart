import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/pages/notes/admin_markdown_editor.dart';

void main() {
  Widget editor(TextEditingController controller, MarkdownPreviewLoader loader,
          {bool enabled = true, String kind = 'markdown'}) =>
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: AdminMarkdownEditor(
              controller: controller,
              label: '正文',
              kind: kind,
              enabled: enabled,
              minLines: 2,
              maxLines: 4,
              previewLoader: loader,
            ),
          ),
        ),
      );

  testWidgets('explicit preview clears on edits and ignores stale responses',
      (WidgetTester tester) async {
    final TextEditingController controller = TextEditingController(text: '甲');
    addTearDown(controller.dispose);
    final List<Completer<String>> calls = <Completer<String>>[];
    final List<String> kinds = <String>[];
    Future<String> loader(String text, String kind) {
      kinds.add('$kind:$text');
      final Completer<String> pending = Completer<String>();
      calls.add(pending);
      return pending.future;
    }
    await tester.pumpWidget(editor(controller, loader, kind: 'card'));
    expect(calls, isEmpty);
    await tester.tap(find.text('预览（不保存）'));
    await tester.pump();
    expect(kinds, <String>['card:甲']);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    controller.text = '乙';
    await tester.pump();
    expect(find.byType(LinearProgressIndicator), findsNothing);
    await tester.tap(find.text('预览（不保存）'));
    await tester.pump();
    expect(kinds, <String>['card:甲', 'card:乙']);
    calls.first.complete('<p>旧结果</p>');
    await tester.pump();
    expect(find.text('预览（未保存）'), findsNothing);
    calls.last.complete('<p>新结果</p>');
    await tester.pump();
    expect(find.text('预览（未保存）'), findsOneWidget);
    controller.text = '丙';
    await tester.pump();
    expect(find.text('预览（未保存）'), findsNothing);
  });

  testWidgets('preview errors do not save and editing clears the error',
      (WidgetTester tester) async {
    final TextEditingController controller = TextEditingController(text: '正文');
    addTearDown(controller.dispose);
    await tester.pumpWidget(editor(controller,
        (String text, String kind) async => throw StateError('preview unavailable')));
    await tester.tap(find.text('预览（不保存）'));
    await tester.pump();
    expect(find.textContaining('preview unavailable'), findsOneWidget);
    controller.text = '修改';
    await tester.pump();
    expect(find.textContaining('preview unavailable'), findsNothing);
    await tester.pumpWidget(editor(controller,
        (String text, String kind) async => '<p>ignored</p>', enabled: false));
    final Finder previewButton = find.ancestor(
        of: find.text('预览（不保存）'),
        matching: find.byWidgetPredicate((Widget widget) => widget is TextButton));
    expect(tester.widget<TextButton>(previewButton).onPressed, isNull);
  });

  testWidgets('preview limits input before any request',
      (WidgetTester tester) async {
    final TextEditingController controller = TextEditingController(
        text: List<String>.filled(20001, '医').join());
    addTearDown(controller.dispose);
    int requests = 0;
    await tester.pumpWidget(editor(controller, (String text, String kind) async {
      requests++;
      return '<p>ignored</p>';
    }));
    await tester.tap(find.text('预览（不保存）'));
    await tester.pump();
    expect(requests, 0);
    expect(find.textContaining('20,000'), findsOneWidget);
  });

  testWidgets('toolbar keeps a reverse Unicode selection across taps',
      (WidgetTester tester) async {
    final TextEditingController controller = TextEditingController(text: '前😀后');
    addTearDown(controller.dispose);
    await tester.pumpWidget(editor(controller,
        (String text, String kind) async => '<p>ignored</p>'));
    await tester.tap(find.byType(TextField).first);
    await tester.pump();
    controller.selection = const TextSelection(baseOffset: 3, extentOffset: 1);
    await tester.tap(find.text('高亮选区'));
    await tester.pump();
    expect(controller.text, '前==😀==后');
    expect(controller.selection.baseOffset, 5);
    expect(controller.selection.extentOffset, 3);
    await tester.tap(find.text('移除高亮'));
    await tester.pump();
    expect(controller.text, '前😀后');
    expect(controller.selection.baseOffset, 3);
    expect(controller.selection.extentOffset, 1);
  });

  testWidgets('table dialog edits and inserts without losing selected text',
      (WidgetTester tester) async {
    final TextEditingController controller = TextEditingController(text: '前😀后');
    addTearDown(controller.dispose);
    await tester.pumpWidget(editor(controller,
        (String text, String kind) async => '<p>preview</p>'));
    controller.selection = const TextSelection(baseOffset: 3, extentOffset: 1);
    await tester.tap(find.text('插入表格').first);
    await tester.pumpAndSettle();
    expect(find.text('列 2 / 6 · 行 1 / 12'), findsOneWidget);
    await tester.tap(find.text('添加列'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('添加行'));
    await tester.pumpAndSettle();
    expect(find.text('列 3 / 6 · 行 2 / 12'), findsOneWidget);
    await tester.enterText(find.byKey(const ValueKey<String>('table-header-0')), 'A|B');
    await tester.enterText(find.byKey(const ValueKey<String>('table-cell-0-0')), '医\n学');
    await tester.tap(find.text('插入表格').last);
    await tester.pumpAndSettle();
    expect(controller.text, startsWith('前\n\n| A&#124;B |'));
    expect(controller.text, contains('| 医<br>学 |'));
    expect(controller.text, endsWith('😀后'));
    expect(controller.selection.isCollapsed, isTrue);
  });
}
