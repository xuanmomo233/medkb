import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart' hide Card;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../lib/api.dart';
import '../lib/models.dart';
import '../lib/nav.dart';
import '../lib/option_labels.dart';
import '../lib/pages/cards/source_questions_page.dart';
import '../lib/pages/quiz/option_tile.dart';
import '../lib/pages/quiz/quiz_session.dart';
import '../lib/pages/notes/admin_edit_sheet.dart';
import '../lib/pages/notes/admin_markdown_editor.dart';

const List<String> labels = <String>['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K'];

Map<String, dynamic> questionJson({String answer = 'J', bool labeled = true}) => <String, dynamic>{
  'id': 7, 'qid': 'Q7', 'stem_html': '题干',
  'options_html': List<String>.generate(10, (int i) => '选项${i + 1}'),
  if (labeled) 'option_labels': labels,
  'answer': answer, 'done': true, 'last_picked': 'A', 'starred': true,
};

http.Response jsonResponse(Object body) => http.Response(jsonEncode(body), 200,
    headers: <String, String>{'content-type': 'application/json; charset=utf-8'});

void main() {
  setUp(() => SharedPreferences.setMockInitialValues(<String, Object>{}));

  test('models keep non-contiguous labels and legacy responses generate all sequential labels', () {
    final Question q = Question.fromJson(questionJson());
    expect(q.optionLabels, labels);
    expect(hasOptionsQ(q), isTrue);
    expect(lettersToIdx('JK', q), <int>[8, 9]);
    expect(lettersToIdx('I', q), isEmpty);
    final Question legacy = Question.fromJson(questionJson(labeled: false));
    expect(legacy.optionLabels, 'ABCDEFGHIJ'.split(''));
    expect(Question.fromJson(<String, dynamic>{...questionJson(), 'option_labels': <String>[]}).optionLabels,
        'ABCDEFGHIJ'.split(''));
    expect(() => readOptionLabels(<String>[], 27), throwsFormatException);
    expect(lettersToIdx('IJ', legacy), <int>[8, 9]);
    final AdminQuestion admin = AdminQuestion.fromJson(<String, dynamic>{
      'id': 7, 'options': q.optionsHtml, 'option_labels': labels,
    });
    expect(admin.optionLabels, labels);
    expect(() => readOptionLabels(<String>['A', 'A'], 2), throwsFormatException);
    expect(() => Question.fromJson(<String, dynamic>{...questionJson(), 'option_labels': <String>['A']}),
        throwsFormatException);
  });

  test('administrator option edits preserve labels, support explicit deletion and generate legacy labels', () {
    final List<String> options = List<String>.generate(10, (int i) => '内容${i + 1}');
    final LabeledOptions unchanged = parseOptionLines(formatOptionLines(options, labels), labels);
    expect(unchanged.options, options);
    expect(unchanged.labels, labels);
    final LabeledOptions edited = parseOptionLines('A. 甲\nJ. 乙\nK. 丙', labels);
    expect(edited.options, <String>['甲', '乙', '丙']);
    expect(edited.labels, <String>['A', 'J', 'K']);
    expect(AdminQuestionPatch(options: edited.options, optionLabels: edited.labels).toJson(),
        <String, dynamic>{'options': <String>['甲', '乙', '丙'], 'option_labels': <String>['A', 'J', 'K']});
    expect(parseOptionLines(options.join('\n'), labels).labels, labels);
    expect(() => parseOptionLines('甲\n乙', labels), throwsFormatException);
    expect(() => parseOptionLines('A. 甲\n乙', labels), throwsFormatException);
    expect(() => parseOptionLines('A. 甲\nA. 乙', labels), throwsFormatException);
    expect(parseOptionLines('甲\n乙\n丙', <String>['A', 'B']).labels, <String>['A', 'B', 'C']);
    expect(const AdminQuestionPatch(answer: 'J').toJson(), <String, dynamic>{'answer': 'J'});
  });

  test('practice submits J as its actual array index and rejects absent I', () async {
    final Completer<Map<String, dynamic>> posted = Completer<Map<String, dynamic>>();
    final Question q = Question.fromJson(questionJson());
    final QuizSession session = QuizSession(const QuizRunArgs(ids: <int>[7]), (_) {});
    session.questions = <Question>[q];
    session.status = RunStatus.ready;
    await http.runWithClient(() async {
      session.pick(q, 'I');
      expect(session.ans, isEmpty);
      session.pick(q, 'J');
      expect(session.ans[7]!.correct, isTrue);
      final Map<String, dynamic> body = await posted.future;
      expect(body, <String, dynamic>{'question_id': 7, 'picked': <int>[8]});
      session.dispose();
    }, () => MockClient((http.Request request) async {
      if (request.method == 'POST') {
        expect(request.url.path, '/api/quiz/attempts');
        posted.complete(jsonDecode(request.body) as Map<String, dynamic>);
        return jsonResponse(<String, dynamic>{'correct': true, 'answer': 'J', 'stat': <String, dynamic>{}});
      }
      return jsonResponse(questionJson());
    }));
  });

  test('multiple-answer exam submits J and K as positions 8 and 9', () async {
    final Question q = Question.fromJson(questionJson(answer: 'J、K'));
    final QuizSession session = QuizSession(const QuizRunArgs(ids: <int>[7], mode: QuizMode.test), (_) {});
    session.questions = <Question>[q];
    session.status = RunStatus.ready;
    expect(isMultiQ(q), isTrue);
    await http.runWithClient(() async {
      session.pick(q, 'K');
      session.pick(q, 'J');
      expect(session.ans[7]!.picked, 'JK');
      expect(session.ans[7]!.judged, isFalse);
      expect(await session.submit(), isNotNull);
      session.dispose();
    }, () => MockClient((http.Request request) async {
      expect(request.url.path, '/api/quiz/submit');
      final Map<String, dynamic> body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body['items'], <Map<String, dynamic>>[<String, dynamic>{'question_id': 7, 'picked': <int>[8, 9]}]);
      return jsonResponse(<String, dynamic>{'total': 1, 'correct': 1, 'score_100': 100});
    }));
  });

  test('historical separated and full-width answers judge by labels without rewriting the source', () async {
    final Question q = Question.fromJson(questionJson(answer: 'ｊ、Ｋ'));
    expect(answerOptionLetters(q.answer), 'JK');
    expect(answerOptionLetters(' K / J;J '), 'JK');
    expect(answerOptionLetters('答案为J'), isEmpty);
    expect(hasOptionsQ(q), isTrue);
    expect(isMultiQ(q), isTrue);
    final Completer<void> posted = Completer<void>();
    final QuizSession session = QuizSession(const QuizRunArgs(ids: <int>[7]), (_) {});
    session.questions = <Question>[q];
    session.status = RunStatus.ready;
    await http.runWithClient(() async {
      session.pick(q, 'J');
      session.pick(q, 'K');
      session.confirmMulti(q);
      expect(session.ans[7]!.correct, isTrue);
      expect(q.answer, 'ｊ、Ｋ');
      await posted.future;
      session.dispose();
    }, () => MockClient((http.Request request) async {
      if (request.method == 'POST') {
        expect((jsonDecode(request.body) as Map<String, dynamic>)['picked'], <int>[8, 9]);
        posted.complete();
      }
      return jsonResponse(<String, dynamic>{'correct': true, 'answer': q.answer});
    }));
  });

  test('detail refresh updates options and labels together and preserves metadata for old responses', () async {
    final QuizSession session = QuizSession(const QuizRunArgs(ids: <int>[7]), (_) {});
    final Question original = Question.fromJson(questionJson());
    session.questions = <Question>[original];
    session.ans[7] = const Ans('J', true, true);
    int reads = 0;
    await http.runWithClient(() async {
      await session.refreshFull(7);
      expect(session.questions.single.optionLabels, labels);
      expect(session.questions.single.optionsHtml, original.optionsHtml);
      expect(session.ans[7]!.picked, 'J');
      await session.refreshFull(7);
      expect(session.questions.single.optionsHtml, <String>['甲', '乙', '丙']);
      expect(session.questions.single.optionLabels, <String>['A', 'J', 'K']);
      expect(session.questions.single.answer, 'K');
      expect(session.questions.single.lastPicked, 'A');
      expect(session.questions.single.done, isTrue);
      expect(session.questions.single.starred, isTrue);
      expect(session.full[7]!.optionLabels, <String>['A', 'J', 'K']);
      expect(session.ans, isEmpty, reason: '选项/标签/答案改变后，本轮旧选择不能覆盖新语义');
      session.dispose();
    }, () => MockClient((http.Request request) async {
      reads++;
      return jsonResponse(<String, dynamic>{
        'id': 7, 'answer': reads == 1 ? 'J' : 'K', 'stem_html': '新题干',
        if (reads > 1) 'options_html': <String>['甲', '乙', '丙'],
        if (reads > 1) 'option_labels': <String>['A', 'J', 'K'],
      });
    }));
  });

  test('exam resume rejects saved choices after option text changes even when labels and answer stay the same', () async {
    const QuizRunArgs args = QuizRunArgs(ids: <int>[7], mode: QuizMode.test, continueKey: 'label-cache-check');
    int version = 1;
    await http.runWithClient(() async {
      final QuizSession first = QuizSession(args, (_) {});
      await first.load();
      first.pick(first.questions.single, 'J');
      await Future<void>.delayed(Duration.zero);
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String saved = prefs.getString(Api.prefKey('qtest', 'label-cache-check'))!;
      expect((jsonDecode(saved) as Map<String, dynamic>)['picks'], <String, dynamic>{'7': 'J'});
      first.dispose();
      version = 2;
      final QuizSession reopened = QuizSession(args, (_) {});
      await reopened.load();
      expect(reopened.questions.single.optionLabels, labels);
      expect(reopened.questions.single.answer, 'J');
      expect(reopened.ans, isEmpty);
      reopened.dispose();
    }, () => MockClient((http.Request request) async {
      final Map<String, dynamic> q = questionJson();
      if (version == 2) q['options_html'] = <String>['新内容', ...(q['options_html'] as List<String>).skip(1)];
      return jsonResponse(<Map<String, dynamic>>[q]);
    }));
  });

  testWidgets('all ten options render with J/K and selection uses the visible source label', (WidgetTester tester) async {
    String? picked;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: OptionList(
      q: Question.fromJson(questionJson()), picked: '', judged: false, reveal: false,
      stat: null,
      onPick: (String letter) => picked = letter,
    )))));
    expect(find.byType(OptionTile), findsNWidgets(10));
    expect(find.text('I'), findsNothing);
    expect(find.text('J'), findsOneWidget);
    expect(find.text('K'), findsOneWidget);
    await tester.ensureVisible(find.text('K'));
    await tester.tap(find.text('K'));
    expect(picked, 'K');
  });

  testWidgets('source-question preview shows original J/K instead of continuous I/J', (WidgetTester tester) async {
    await http.runWithClient(() async {
      await tester.pumpWidget(MaterialApp(home: SourceQuestionsPage(list: <SourceQuestion>[
        SourceQuestion.fromJson(<String, dynamic>{'id': 7, 'qid': 'Q7'}),
      ])));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('K'), 250, scrollable: find.byType(Scrollable).last);
      expect(find.text('K'), findsOneWidget);
      expect(find.text('I'), findsNothing);
    }, () => MockClient((http.Request request) async => jsonResponse(<Map<String, dynamic>>[questionJson()])));
  });

  testWidgets('administrator editor displays source labels and sends labels with changed options', (WidgetTester tester) async {
    final bool wasAdmin = Api.admin;
    Api.admin = true;
    addTearDown(() => Api.admin = wasAdmin);
    Map<String, dynamic>? patch;
    await http.runWithClient(() async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (BuildContext context) =>
        TextButton(onPressed: () => showAdminEditSheet(context, 7), child: const Text('打开编辑')),
      ))));
      await tester.tap(find.text('打开编辑'));
      await tester.pumpAndSettle();
      final Finder options = find.byWidgetPredicate((Widget widget) => widget is TextField && widget.decoration?.labelText == '选项');
      final TextEditingController controller = tester.widget<TextField>(options).controller!;
      expect(controller.text, contains('J. 选项9'));
      expect(controller.text, isNot(contains('I.')));
      controller.text = 'A. 甲\nJ. 乙\nK. 丙';
      await tester.tap(find.text('保存'));
      await tester.pumpAndSettle();
      expect(patch!['options'], <String>['甲', '乙', '丙']);
      expect(patch!['option_labels'], <String>['A', 'J', 'K']);
      expect(patch!.containsKey('answer'), isFalse);
    }, () => MockClient((http.Request request) async {
      if (request.method == 'GET') {
        return jsonResponse(<String, dynamic>{
          'id': 7, 'options': questionJson()['options_html'], 'option_labels': labels, 'answer': 'J',
        });
      }
      expect(request.method, 'PUT');
      expect(request.url.path, '/api/admin/questions/7');
      patch = jsonDecode(request.body) as Map<String, dynamic>;
      return jsonResponse(<String, dynamic>{'changed': 2});
    }));
  });

  testWidgets('editing only analysis never resubmits a lowercase or full-width original answer', (WidgetTester tester) async {
    final bool wasAdmin = Api.admin;
    Api.admin = true;
    addTearDown(() => Api.admin = wasAdmin);
    Map<String, dynamic>? patch;
    await http.runWithClient(() async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (BuildContext context) =>
        TextButton(onPressed: () => showAdminEditSheet(context, 7), child: const Text('打开编辑')),
      ))));
      await tester.tap(find.text('打开编辑'));
      await tester.pumpAndSettle();
      final Finder scrollable = find.descendant(of: find.byType(ListView).last, matching: find.byType(Scrollable)).first;
      await tester.scrollUntilVisible(find.text('解析（Markdown 原文）'), 250, scrollable: scrollable);
      final Finder editor = find.byWidgetPredicate((Widget widget) => widget is AdminMarkdownEditor && widget.label == '解析（Markdown 原文）');
      tester.widget<AdminMarkdownEditor>(editor).controller.text = '新解析';
      await tester.tap(find.text('保存'));
      await tester.pumpAndSettle();
      expect(patch, <String, dynamic>{'analysis': '新解析'});
    }, () => MockClient((http.Request request) async {
      if (request.method == 'GET') {
        return jsonResponse(<String, dynamic>{
          'id': 7, 'options': questionJson()['options_html'], 'option_labels': labels, 'answer': 'ｊ、Ｋ',
        });
      }
      patch = jsonDecode(request.body) as Map<String, dynamic>;
      return jsonResponse(<String, dynamic>{'changed': 1});
    }));
  });
}
