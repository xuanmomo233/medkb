import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/api.dart';
import 'package:medkb/models.dart';
import 'package:medkb/pages/today/schedule_session.dart';
import 'package:shared_preferences/shared_preferences.dart';

Question question({List<String> options = const <String>['甲', '乙', '丙']}) =>
    Question.fromJson(<String, dynamic>{
      'id': 7,
      'qid': 'Q7',
      'stem_html': '题干',
      'options_html': options,
      'option_labels': <String>['A', 'J', 'K'],
      'answer': 'J',
    });

ScheduleSession session(String day) => ScheduleSession(
      items: const <ScheduleItem>[],
      index: 0,
      day: day,
    );

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    Api.base = 'https://medkb.example.test';
    Api.token = 'account-a';
  });

  test('retains answers and card state only for the same account and day', () async {
    final Question q = question();
    final ScheduleSession original = session('2026-10-31');
    original.saveAnswer(q, 'J', true, true);
    original.saveCard(101, rating: MarkAction.rateGood, flipped: true);
    original.dispose();

    final ScheduleSession sameAccountAndDay = session('2026-10-31');
    await sameAccountAndDay.load();
    expect(sameAccountAndDay.answerFor(q)?['picked'], 'J');
    expect(sameAccountAndDay.ratings[101], MarkAction.rateGood);
    expect(sameAccountAndDay.flippedCards, contains(101));
    sameAccountAndDay.dispose();

    final ScheduleSession anotherDay = session('2026-11-01');
    await anotherDay.load();
    expect(anotherDay.savedAnswer(7), isNull);
    expect(anotherDay.ratings, isEmpty);
    expect(anotherDay.flippedCards, isEmpty);
    anotherDay.dispose();

    Api.token = 'account-b';
    final ScheduleSession anotherAccount = session('2026-10-31');
    await anotherAccount.load();
    expect(anotherAccount.savedAnswer(7), isNull);
    expect(anotherAccount.ratings, isEmpty);
    expect(anotherAccount.flippedCards, isEmpty);
    anotherAccount.dispose();
  });

  test('invalidates a restored answer when question content changes', () async {
    final Question original = question();
    final ScheduleSession saved = session('2026-10-31');
    saved.saveAnswer(original, 'J', true, true);
    saved.dispose();

    final ScheduleSession restored = session('2026-10-31');
    await restored.load();
    expect(restored.savedAnswer(7), isNotNull);
    final Question changed = question(options: const <String>['新版甲', '乙', '丙']);
    expect(restored.answerFor(changed), isNull);
    expect(restored.savedAnswer(7), isNull);
    restored.dispose();
  });
}
