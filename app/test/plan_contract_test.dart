import 'package:flutter_test/flutter_test.dart';
import '../lib/models.dart';
import '../lib/nav.dart';

void main() {
  test('plan uses unique pending counts instead of adding overlapping sections', () {
    final PlanToday plan = PlanToday.fromJson(<String, dynamic>{
      'configured': true,
      'today_questions': 3,
      'today_cards': 1,
      'pending_questions': 5,
      'pending_cards': 2,
      'scheduled_days': <int>[1, 2, 3],
      'items': <dynamic>[],
      'today_items': <dynamic>[],
    });
    expect(plan.todayQuestions, 3);
    expect(plan.todayCards, 1);
    expect(plan.pendingQuestions, 5);
    expect(plan.scheduledDays, <int>[1, 2, 3]);
  });

  test('related practice carries fresh flag and plan detail carries its day', () {
    final Map<String, Object?> related = const QuizRunArgs(ids: <int>[7], fresh: true).toQuery().toQuery();
    expect(related['fresh'], isTrue);
    final Map<String, Object?> plan = const QuizRunArgs(ids: <int>[7], planDay: 1).toQuery().toQuery();
    expect(plan['plan_day'], 1);
    expect(plan['ids'], <int>[7]);
  });

  test('related preview has a reason and plan membership without answers', () {
    final RelatedQuestion item = RelatedQuestion.fromJson(<String, dynamic>{
      'id': 7, 'stem': '题干摘要', 'label': '同考法变式',
      'reason': '改变判断条件', 'in_plan': true,
    });
    expect(item.id, 7);
    expect(item.inPlan, isTrue);
    expect(item.reason, '改变判断条件');
  });
}
