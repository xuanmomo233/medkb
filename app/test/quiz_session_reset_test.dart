import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../lib/api.dart';
import '../lib/nav.dart';
import '../lib/pages/quiz/quiz_session.dart';

void main() {
  test('historical answers stay hidden and temporary reset preserves source history', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final HttpServer server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((HttpRequest request) async {
      request.response.headers.contentType = ContentType.json;
      request.response.write(jsonEncode(<Map<String, dynamic>>[
        <String, dynamic>{
          'id': 7, 'qid': 'Q7', 'stem_html': '题干', 'options_html': <String>['甲', '乙'],
          'answer': 'A', 'done': true, 'last_picked': 'A', 'last_correct': true, 'starred': true,
        },
      ]));
      await request.response.close();
    });
    final String previousBase = Api.base;
    Api.base = 'http://127.0.0.1:${server.port}';
    final QuizSession session = QuizSession(const QuizRunArgs(ids: <int>[7]), (_) {});
    try {
      await session.load();
      expect(session.questions.single.done, isTrue);
      expect(session.questions.single.lastPicked, 'A');
      expect(session.ans, isEmpty);
      expect(session.showFull(session.questions.single), isFalse);
      session.ans[7] = const Ans('A', true, true);
      await session.resetSession();
      expect(session.ans, isEmpty);
      expect(session.questions.single.lastPicked, 'A');
      expect(session.questions.single.starred, isTrue);
      expect(session.idx, 0);
    } finally {
      session.dispose();
      Api.base = previousBase;
      await server.close(force: true);
    }
  });
}
