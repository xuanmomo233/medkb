import 'package:flutter/material.dart';
import 'models.dart';
import 'pages/browse/chapter_page.dart';
import 'pages/browse/search_page.dart';
import 'pages/cards/card_run_page.dart';
import 'pages/notes/admin_edit_sheet.dart';
import 'pages/notes/note_sheet.dart';
import 'pages/quiz/exam_report_page.dart';
import 'pages/quiz/exams_page.dart';
import 'pages/quiz/quiz_pool_page.dart';
import 'pages/quiz/quiz_run_page.dart';
import 'pages/quiz/wrong_book_page.dart';

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
  const CardRunArgs({
    this.subject,
    this.part,
    this.ids,
    this.planDay,
    this.starred = false,
    this.due = false,
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
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => QuizRunPage(args)));

Future<void> openCardRun(BuildContext context, CardRunArgs args) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => CardRunPage(args)));

Future<void> openChapter(BuildContext context, int id) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => ChapterPage(id)));

Future<void> openSearch(BuildContext context, String q) =>
    Navigator.of(context).push<void>(MaterialPageRoute<void>(
        builder: (_) => SearchPage(initialQuery: q)));

Future<void> openNotes(BuildContext context,
        {required String targetType, required int targetId}) =>
    showNoteSheet(context, targetType: targetType, targetId: targetId);

Future<void> openAdminEdit(BuildContext context, int questionId) =>
    showAdminEditSheet(context, questionId);

Future<void> openWrongBook(BuildContext context) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => const WrongBookPage()));

Future<void> openExams(BuildContext context) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => const ExamsPage()));

Future<void> openQuizPool(BuildContext context, QuizFilter filter) =>
    Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => QuizPoolPage(filter)));

Future<void> openExamReport(
        BuildContext context, ExamReport report, String title) =>
    Navigator.of(context).push<void>(MaterialPageRoute<void>(
        builder: (_) => ExamReportPage(report, title)));
