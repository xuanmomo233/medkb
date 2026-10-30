import 'package:flutter/material.dart';
import 'models.dart';
import 'endpoints.dart';
import 'pages/browse/chapter_page.dart';
import 'pages/browse/search_page.dart';
import 'pages/cards/card_run_page.dart';
import 'pages/notes/admin_edit_sheet.dart';
import 'pages/notes/admin_card_edit_sheet.dart';
import 'pages/notes/note_sheet.dart';
import 'pages/quiz/exam_report_page.dart';
import 'pages/quiz/exams_page.dart';
import 'pages/quiz/quiz_pool_page.dart';
import 'pages/quiz/quiz_run_page.dart';
import 'pages/quiz/wrong_book_page.dart';
import 'pages/today/schedule_session.dart';
import 'pages/today/schedule_run_page.dart';

/// 刷题会话参数：各字段按优先级由服务端 /quiz/questions 解析（ids > planDay > 其余筛选）
class QuizRunArgs {
  final QuizFilter? filter;
  final List<int>? ids;
  final int? planDay;
  final bool starred;
  final bool wrong;
  final bool due;
  final bool random;
  final bool shuffle;
  final bool fresh;
  final List<ScheduleItem> scheduleItems;
  final int scheduleIndex;
  final ScheduleSession? scheduleSession;
  final int? initialQuestionId;
  final bool exactIds;
  final bool allowAnswerReveal;

  /// QuizMode 常量：practice / recite / quick / test
  final String mode;
  final String? title;

  /// 模考限时（分钟），null 表示不限时
  final int? mins;

  /// 进度续做的持久键（相同 key 恢复上次位置）
  final String? continueKey;
  const QuizRunArgs({
    this.filter,
    this.ids,
    this.planDay,
    this.starred = false,
    this.wrong = false,
    this.due = false,
    this.random = false,
    this.shuffle = false,
    this.fresh = false,
    this.scheduleItems = const <ScheduleItem>[],
    this.scheduleIndex = 0,
    this.scheduleSession,
    this.initialQuestionId,
    this.exactIds = false,
    this.allowAnswerReveal = false,
    this.mode = QuizMode.practice,
    this.title,
    this.mins,
    this.continueKey,
  });

  QuizQuery toQuery({int? limit}) => QuizQuery(
        filter: filter ?? const QuizFilter(),
        ids: ids,
        planDay: planDay,
        starred: starred,
        wrong: wrong,
        due: due,
        random: random,
        shuffle: shuffle,
        fresh: fresh,
        limit: limit,
      );
}

class CardRunArgs {
  final String? subject;
  final String? part;
  final List<int>? ids;
  final int? planDay;
  final bool starred;
  final bool due;
  final List<ScheduleItem> scheduleItems;
  final int scheduleIndex;
  final ScheduleSession? scheduleSession;
  const CardRunArgs({
    this.subject,
    this.part,
    this.ids,
    this.planDay,
    this.starred = false,
    this.due = false,
    this.scheduleItems = const <ScheduleItem>[],
    this.scheduleIndex = 0,
    this.scheduleSession,
  });

  CardQuery toQuery() => CardQuery(
        subject: subject,
        part: part,
        ids: ids,
        planDay: planDay,
        starred: starred,
        due: due,
      );
}

Future<void> openQuizRun(BuildContext context, QuizRunArgs args) =>
    Navigator.of(context)
        .push<void>(MaterialPageRoute<void>(builder: (_) => QuizRunPage(args)));

Future<void> openScheduleItem(
    BuildContext context, List<ScheduleItem> items, int index,
    {bool replace = false, String? day}) {
  if (index < 0 || index >= items.length) return Future<void>.value();
  final MaterialPageRoute<void> route = MaterialPageRoute<void>(
      builder: (_) =>
          ScheduleRunPage(items: items, initialIndex: index, day: day));
  return replace
      ? Navigator.of(context).pushReplacement<void, void>(route)
      : Navigator.of(context).push<void>(route);
}

Future<void> nextScheduleItem(
    BuildContext context, List<ScheduleItem> items, int index) async {
  final ScheduleToday today = await Endpoints.scheduleToday();
  if (!context.mounted) return;
  final int current = today.items
      .indexWhere((ScheduleItem item) => item.matchesId(items[index].id));
  if (current >= 0 && current + 1 < today.items.length) {
    await openScheduleItem(context, today.items, current + 1,
        replace: true, day: today.day);
    return;
  }
  if (context.mounted) Navigator.of(context).maybePop();
}

Future<void> openCardRun(BuildContext context, CardRunArgs args) =>
    Navigator.of(context)
        .push<void>(MaterialPageRoute<void>(builder: (_) => CardRunPage(args)));

Future<void> openChapter(BuildContext context, int id) => Navigator.of(context)
    .push<void>(MaterialPageRoute<void>(builder: (_) => ChapterPage(id)));

Future<void> openSearch(BuildContext context, String q) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => SearchPage(initialQuery: q)));

Future<void> openNotes(BuildContext context,
        {required String targetType, required int targetId}) =>
    showNoteSheet(context, targetType: targetType, targetId: targetId);

Future<bool> openAdminEdit(BuildContext context, int questionId) =>
    showAdminEditSheet(context, questionId);

Future<bool> openAdminCardEdit(BuildContext context, int cardId) =>
    showAdminCardEditSheet(context, cardId);

Future<void> openWrongBook(BuildContext context) => Navigator.of(context)
    .push<void>(MaterialPageRoute<void>(builder: (_) => const WrongBookPage()));

Future<void> openExams(BuildContext context) => Navigator.of(context)
    .push<void>(MaterialPageRoute<void>(builder: (_) => const ExamsPage()));

Future<void> openQuizPool(BuildContext context, QuizFilter filter) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => QuizPoolPage(filter)));

Future<void> openExamReport(
        BuildContext context, ExamReport report, String title) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => ExamReportPage(report, title)));
