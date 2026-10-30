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

  test('today sections report only tasks due on the current plan day', () {
    final PlanToday plan = PlanToday.fromJson(<String, dynamic>{
      'configured': true,
      'today_questions': 4,
      'today_cards': 2,
      'today_sections': <dynamic>[
        <String, dynamic>{
          'key': '内科学|呼吸系统疾病',
          'subject': '内科学',
          'part': '呼吸系统疾病',
          'label': '内科学 · 呼吸系统疾病',
          'cards': 2,
          'questions': 4,
        },
      ],
      'items': <dynamic>[
        <String, dynamic>{
          'key': '内科学|呼吸系统疾病',
          'subject': '内科学',
          'part': '呼吸系统疾病',
          'label': '内科学 · 呼吸系统疾病',
          'cards': 294,
          'card_done': 4,
          'questions': 849,
          'question_done': 21,
          'done': false,
          'day': 1,
        },
      ],
      'today_items': <dynamic>[],
    });

    expect(plan.todayQuestions, 4);
    expect(plan.todayCards, 2);
    expect(plan.todaySections, hasLength(1));
    expect(plan.todaySections.single.cards, 2);
    expect(plan.todaySections.single.questions, 4);
    expect(plan.items.single.questions, 849);
  });

  test("post-replan D2 summary matches today's task and section totals", () {
    final PlanToday plan = PlanToday.fromJson(<String, dynamic>{
      'configured': true,
      'start': '2026-10-24',
      'day_no': 2,
      'today_cards': 256,
      'today_questions': 291,
      'today_sections': <dynamic>[
        <String, dynamic>{
          'key': '内科学|01-呼吸系统疾病',
          'subject': '内科学',
          'part': '01-呼吸系统疾病',
          'label': '内科学 · 01-呼吸系统疾病',
          'cards': 33,
          'questions': 51,
        },
        <String, dynamic>{
          'key': '02',
          'subject': '内科学',
          'part': '02-循环系统疾病',
          'label': '循环',
          'cards': 53,
          'questions': 63,
        },
        <String, dynamic>{
          'key': '03',
          'subject': '内科学',
          'part': '03-消化系统疾病',
          'label': '消化',
          'cards': 34,
          'questions': 44,
        },
        <String, dynamic>{
          'key': '04',
          'subject': '内科学',
          'part': '04-泌尿系统疾病',
          'label': '泌尿',
          'cards': 25,
          'questions': 34,
        },
        <String, dynamic>{
          'key': '05',
          'subject': '内科学',
          'part': '05-血液系统疾病',
          'label': '血液',
          'cards': 30,
          'questions': 38,
        },
        <String, dynamic>{
          'key': '06',
          'subject': '内科学',
          'part': '06-内分泌与代谢疾病',
          'label': '内分泌',
          'cards': 24,
          'questions': 36,
        },
        <String, dynamic>{
          'key': '07',
          'subject': '内科学',
          'part': '07-风湿免疫疾病',
          'label': '风湿',
          'cards': 13,
          'questions': 18,
        },
        <String, dynamic>{
          'key': '08',
          'subject': '内科学',
          'part': '08-中毒与理化因素',
          'label': '中毒',
          'cards': 8,
          'questions': 7,
        },
        <String, dynamic>{
          'key': '10',
          'subject': '内科学',
          'part': '10-口诀速记',
          'label': '口诀',
          'cards': 36,
          'questions': 0,
        },
      ],
      'day_summaries': <dynamic>[
        <String, dynamic>{
          'no': 1,
          'date': '2026-10-25',
          'cards': 256,
          'questions': 291,
          'overdue_cards': 0,
          'overdue_questions': 0,
        },
        <String, dynamic>{
          'no': 2,
          'date': '2026-10-26',
          'cards': 255,
          'questions': 292,
          'overdue_cards': 0,
          'overdue_questions': 0,
        },
      ],
      'items': <dynamic>[],
      'today_items': <dynamic>[],
    });

    expect(plan.dayNo, 2);
    expect(plan.currentDate, '2026-10-25');
    expect(plan.todayCount, 547);
    expect(plan.dueTodayCount, 547);
    expect(plan.overdueCount, 0);
    expect(plan.todaySections.fold<int>(0, (n, s) => n + s.cards), plan.todayCards);
    expect(plan.todaySections.fold<int>(0, (n, s) => n + s.questions), plan.todayQuestions);
    expect(plan.summaryForRelativeDay(1)?.cards, 256);
    expect(plan.summaryForRelativeDay(1)?.questions, 291);
    expect(plan.summaryForRelativeDay(2)?.cards, 255);
    expect(plan.summaryForRelativeDay(2)?.questions, 292);
    expect(plan.planDayForRelativeDay(2), 3);
    expect(plan.dateForRelativeDay(2), '2026-10-26');
  });

  test('today summary separates overdue work from current-date work', () {
    // Derived from RR/RO snapshot 3585858 (catalog 0497b113): 493 overdue + 494 due today.
    final PlanToday plan = PlanToday.fromJson(<String, dynamic>{
      'configured': true,
      'start': '2026-10-24',
      'day_no': 2,
      'today_cards': 460,
      'today_questions': 527,
      'day_summaries': <dynamic>[
        <String, dynamic>{
          'no': 1,
          'date': '2026-10-25',
          'cards': 460,
          'questions': 527,
          'overdue_cards': 230,
          'overdue_questions': 263,
        },
      ],
      'items': <dynamic>[],
      'today_items': <dynamic>[],
    });

    expect(plan.dayNo, 2);
    expect(plan.currentDate, '2026-10-25');
    expect(plan.planDayForRelativeDay(1), 2);
    expect(plan.dateForRelativeDay(1), '2026-10-25');
    expect(plan.planDayForRelativeDay(2), 3);
    expect(plan.dateForRelativeDay(2), '2026-10-26');
    expect(plan.overdueCount, 493);
    expect(plan.dueTodayCount, 494);
    expect(plan.todayCount, 987);
  });

  test('today date falls back to start date plus plan day when today has no tasks', () {
    final PlanToday plan = PlanToday.fromJson(<String, dynamic>{
      'configured': true,
      'start': '2026-10-24',
      'day_no': 2,
      'today_cards': 0,
      'today_questions': 0,
      'day_summaries': <dynamic>[],
      'items': <dynamic>[],
      'today_items': <dynamic>[],
    });

    expect(plan.currentDate, '2026-10-25');
    expect(plan.planDayForRelativeDay(1), 2);
    expect(plan.dateForRelativeDay(2), '2026-10-26');
    expect(plan.overdueCount, 0);
    expect(plan.dueTodayCount, 0);
    expect(plan.todayCount, 0);
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
