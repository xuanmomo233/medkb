import 'api.dart';
import 'models.dart';

/// 与 web/src/api/endpoints.ts 一一对应；注意本文件的 Card 指 models.dart 的 Card
class Endpoints {
  Endpoints._();

  static List<T> _list<T>(dynamic j, T Function(Map<String, dynamic>) f) =>
      asMapList(j).map(f).toList();

  // ---------- 账号 ----------
  static Future<AuthResult> register(
          String username, String password, String inviteCode) =>
      Api.register(username, password, inviteCode);
  static Future<AuthResult> login(String username, String password) =>
      Api.login(username, password);
  static Future<void> logout() => Api.logout();
  static Future<User> me() async => User.fromJson(asMap(await Api.get('/auth/me')));
  static Future<VersionInfo> version() async =>
      VersionInfo.fromJson(asMap(await Api.get('/version', cache: false)));

  // ---------- 内容 ----------
  static Future<ContentTree> tree() async =>
      ContentTree.fromJson(asMap(await Api.get('/content/tree')));
  static Future<ChapterDetail> chapter(int id) async =>
      ChapterDetail.fromJson(asMap(await Api.get('/content/chapters/$id')));
  static Future<List<SearchHit>> search(String q, {String? kind}) async =>
      _list(await Api.get('/search', query: <String, Object?>{'q': q, 'kind': kind}),
          SearchHit.fromJson);

  // ---------- 背卡 ----------
  static Future<List<CardPartIndex>> cardIndex() async =>
      _list(await Api.get('/cards/index'), CardPartIndex.fromJson);
  static Future<List<Card>> cards(CardQuery q) async =>
      _list(await Api.get('/cards', query: q.toQuery()), Card.fromJson);
  static Future<List<SourceQuestion>> cardSources(int id) async =>
      _list(await Api.get('/cards/$id/sources'), SourceQuestion.fromJson);

  // ---------- 刷题 ----------
  static Future<FacetProgress> facets(QuizFilter f) async => FacetProgress.fromJson(
      asMap(await Api.get('/quiz/facets', query: f.toQuery())));
  static Future<List<Question>> questions(QuizQuery q, {bool lite = false}) async {
    final Map<String, Object?> query = q.toQuery();
    query['lite'] = lite;
    return _list(await Api.get('/quiz/questions', query: query), Question.fromJson);
  }

  static Future<QuestionFull> questionFull(int id) async =>
      QuestionFull.fromJson(asMap(await Api.get('/quiz/questions/$id')));
  static Future<String> aiAnalysis(int id) async {
    final Map<String, dynamic> j =
        asMap(await Api.post('/quiz/questions/$id/ai-analysis', null, 120));
    final Object? h = j['analysis_html'];
    return h is String ? h : '';
  }

  static Future<AttemptResult> attempt(int questionId, List<int> picked) async =>
      AttemptResult.fromJson(asMap(await Api.post('/quiz/attempts', <String, Object?>{
        'question_id': questionId,
        'picked': picked,
      })));
  static Future<ExamReport> submitExam(String title, List<SubmitItem> items) async =>
      ExamReport.fromJson(asMap(await Api.post('/quiz/submit', <String, Object?>{
        'title': title,
        'items': items.map((SubmitItem e) => e.toJson()).toList(),
      })));
  static Future<List<int>> mock({int n = 180}) async {
    final Map<String, dynamic> j =
        asMap(await Api.get('/quiz/mock', query: <String, Object?>{'n': n}, cache: false));
    final Object? ids = j['ids'];
    return ids is List ? ids.whereType<num>().map((num e) => e.toInt()).toList() : <int>[];
  }

  static Future<PoolPage> pool(QuizFilter f,
      {String? flt, int? offset, int? size}) async {
    final Map<String, Object?> query = f.toQuery();
    query['flt'] = flt;
    query['offset'] = offset;
    query['size'] = size;
    return PoolPage.fromJson(asMap(await Api.get('/quiz/pool', query: query)));
  }

  static Future<List<WrongBookGroup>> wrongbook() async =>
      _list(await Api.get('/quiz/wrongbook'), WrongBookGroup.fromJson);
  static Future<List<ExamRecord>> exams() async =>
      _list(await Api.get('/quiz/exams'), ExamRecord.fromJson);

  // ---------- 进度 ----------
  static Future<void> mark(String targetType, int targetId, String action) async {
    await Api.post('/progress/mark', <String, Object?>{
      'target_type': targetType,
      'target_id': targetId,
      'action': action,
    });
  }

  // ---------- 今日 / 计划 / 统计 ----------
  static Future<TodaySummary> today() async =>
      TodaySummary.fromJson(asMap(await Api.get('/today')));
  static Future<int> checkin() async {
    final Map<String, dynamic> j = asMap(await Api.post('/checkin'));
    final Object? s = j['streak'];
    return s is num ? s.toInt() : 0;
  }

  static Future<CalendarMonth> calendar(String month) async => CalendarMonth.fromJson(
      asMap(await Api.get('/calendar', query: <String, Object?>{'month': month})));
  static Future<UserPrefs> prefs() async =>
      UserPrefs.fromJson(asMap(await Api.get('/prefs')));

  /// 仅提交传入的字段；clearExamDate=true 时显式提交 exam_date: null
  static Future<UserPrefs> savePrefs({
    int? dailyGoal,
    String? examDate,
    bool clearExamDate = false,
    int? weakMinSamples,
    double? weakMaxRate,
  }) async {
    final Map<String, Object?> b = <String, Object?>{};
    if (dailyGoal != null) b['daily_goal'] = dailyGoal;
    if (clearExamDate) {
      b['exam_date'] = null;
    } else if (examDate != null) {
      b['exam_date'] = examDate;
    }
    if (weakMinSamples != null) b['weak_min_samples'] = weakMinSamples;
    if (weakMaxRate != null) b['weak_max_rate'] = weakMaxRate;
    return UserPrefs.fromJson(asMap(await Api.put('/prefs', b)));
  }

  static Future<PlanToday> plan() async =>
      PlanToday.fromJson(asMap(await Api.get('/plan')));
  static Future<PlanDayDetail> planDay(int n) async =>
      PlanDayDetail.fromJson(asMap(await Api.get('/plan/days/$n')));
  static Future<void> planRestart() async {
    await Api.post('/plan/restart');
  }

  static Future<List<PlanOption>> planOptions() async =>
      asMapList(await Api.get('/plan/options'))
          .map(PlanOption.fromJson)
          .toList();

  static Future<void> planSaveConfig(
      int totalDays, List<Map<String, String>> items) async {
    await Api.put('/plan/config',
        <String, dynamic>{'total_days': totalDays, 'items': items});
  }

  static Future<void> planClear() async {
    await Api.del('/plan/config');
  }

  static Future<StatsOverview> statsOverview() async =>
      StatsOverview.fromJson(asMap(await Api.get('/stats/overview')));
  static Future<List<WeakSpot>> weakSpots() async =>
      _list(await Api.get('/stats/weakspots'), WeakSpot.fromJson);
  static Future<ScheduleToday> scheduleToday() async =>
      ScheduleToday.fromJson(asMap(await Api.get('/schedule/today')));
  static Future<void> scheduleDone(int id) async {
    await Api.post('/schedule/items/$id/done');
  }

  // ---------- 笔记 ----------
  static Future<List<Note>> notesOf(String targetType, int targetId) async =>
      _list(
          await Api.get('/notes', query: <String, Object?>{
            'target_type': targetType,
            'target_id': targetId,
          }),
          Note.fromJson);
  static Future<List<Note>> notesMine() async =>
      _list(await Api.get('/notes/mine'), Note.fromJson);
  static Future<void> noteAdd(
      String targetType, int targetId, String body, bool isPublic) async {
    await Api.post('/notes', <String, Object?>{
      'target_type': targetType,
      'target_id': targetId,
      'body': body,
      'is_public': isPublic,
    });
  }

  static Future<void> noteDelete(int id) async {
    await Api.del('/notes/$id');
  }

  static Future<List<PublicNote>> publicNotes(String targetType, int targetId) async =>
      _list(
          await Api.get('/notes/public', query: <String, Object?>{
            'target_type': targetType,
            'target_id': targetId,
          }),
          PublicNote.fromJson);
  static Future<NoteLikeResult> noteLike(int id) async =>
      NoteLikeResult.fromJson(asMap(await Api.post('/notes/$id/like')));

  // ---------- AI 陪学 ----------
  static Future<List<ChatMessage>> chatHistory() async =>
      _list(await Api.get('/chat/history'), ChatMessage.fromJson);
  static Future<ChatReply> chatSend(ChatSendBody b) async =>
      ChatReply.fromJson(asMap(await Api.post('/chat/messages', b.toJson(), 180)));
  static Future<ChatAnswerResult> chatAnswer(String qid, String answer) async =>
      ChatAnswerResult.fromJson(asMap(await Api.post('/chat/answer', <String, Object?>{
        'qid': qid,
        'answer': answer,
      }, 120)));
  static Future<void> chatClear() async {
    await Api.del('/chat/history');
  }

  // ---------- 管理员 ----------
  static Future<AdminQuestion> adminQuestion(int id) async =>
      AdminQuestion.fromJson(asMap(await Api.get('/admin/questions/$id', cache: false)));
  static Future<int> adminSaveQuestion(int id, AdminQuestionPatch p) async {
    final Map<String, dynamic> j = asMap(await Api.put('/admin/questions/$id', p.toJson()));
    final Object? c = j['changed'];
    return c is num ? c.toInt() : 0;
  }
  static Future<List<Invite>> adminInvites() async =>
      asMapList(await Api.get('/admin/invites', cache: false))
          .map(Invite.fromJson)
          .toList();
  static Future<List<Invite>> adminNewInvites(int count) async =>
      asMapList(await Api.post('/admin/invites', {'count': count}))
          .map(Invite.fromJson)
          .toList();
  static Future<void> adminRevokeInvite(String code) async {
    await Api.del('/admin/invites/$code');
  }
  static Future<void> changePassword(String oldPw, String newPw) async {
    await Api.put('/auth/password', {'old_password': oldPw, 'new_password': newPw});
  }
  static Future<String> adminSite() async {
    final Map<String, dynamic> j = asMap(await Api.get('/admin/site', cache: false));
    return j['exam_date']?.toString() ?? '2026-12-19';
  }
  static Future<String> adminSaveSite(String? examDate) async {
    final Map<String, dynamic> j =
        asMap(await Api.put('/admin/site', {'exam_date': examDate}));
    return j['exam_date']?.toString() ?? '2026-12-19';
  }
}
