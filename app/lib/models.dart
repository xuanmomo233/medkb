// API v2 类型化模型，与 web/src/api/types.ts 一一对应。注意：本文件的 Card 会与 Material 的 Card 重名，
// 页面中请使用 `import '../../models.dart' hide Card;`（不需要 Card 模型时）或 `as m` 前缀。

import 'option_labels.dart';

Map<String, dynamic> asMap(Object? v) =>
    v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};

List<Map<String, dynamic>> asMapList(Object? v) => v is List
    ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
    : <Map<String, dynamic>>[];

int _i(Object? v) => v is num ? v.toInt() : 0;
int? _in(Object? v) => v is num ? v.toInt() : null;
double _d(Object? v) => v is num ? v.toDouble() : 0.0;
String _s(Object? v) => v is String ? v : '';
String? _sn(Object? v) => v is String ? v : null;
bool _b(Object? v) => v == true;
bool? _bn(Object? v) => v is bool ? v : null;
List<String> _ls(Object? v) =>
    v is List ? v.map((e) => e.toString()).toList() : <String>[];
List<int> _li(Object? v) =>
    v is List ? v.whereType<num>().map((e) => e.toInt()).toList() : <int>[];

// ---------- 枚举型字符串常量（与服务端取值一致） ----------

class ProgressState {
  static const String none = '';
  static const String again = 'again';
  static const String mastered = 'mastered';
  static const String plan = 'plan';
}

class ContentCitation {
  final int id;
  final String sourceKey;
  final String title;
  final String publisher;
  final String edition;
  final String chapter;
  final String section;
  final int? pageStart;
  final int? pageEnd;
  final String note;
  final String status;
  const ContentCitation({
    required this.id,
    required this.sourceKey,
    required this.title,
    required this.publisher,
    required this.edition,
    required this.chapter,
    required this.section,
    required this.pageStart,
    required this.pageEnd,
    required this.note,
    required this.status,
  });
  factory ContentCitation.fromJson(Map<String, dynamic> j) => ContentCitation(
        id: _i(j['id']),
        sourceKey: _s(j['source_key']),
        title: _s(j['title']),
        publisher: _s(j['publisher']),
        edition: _s(j['edition']),
        chapter: _s(j['chapter']),
        section: _s(j['section']),
        pageStart: _in(j['page_start']),
        pageEnd: _in(j['page_end']),
        note: _s(j['note']),
        status: _s(j['status']),
      );
}

class TextbookSource {
  final String key;
  final String title;
  final String subject;
  final String publisher;
  final String edition;

  const TextbookSource({
    required this.key,
    required this.title,
    required this.subject,
    required this.publisher,
    required this.edition,
  });

  factory TextbookSource.fromJson(Map<String, dynamic> j) => TextbookSource(
        key: _s(j['key']),
        title: _s(j['title']),
        subject: _s(j['subject']),
        publisher: _s(j['publisher']),
        edition: _s(j['edition']),
      );
}

class TargetType {
  static const String question = 'question';
  static const String card = 'card';
}

class SearchKind {
  static const String question = 'question';
  static const String card = 'card';
  static const String chapter = 'chapter';
}

class MarkAction {
  static const String star = 'star';
  static const String unstar = 'unstar';
  static const String plan = 'plan';
  static const String unplan = 'unplan';
  static const String seen = 'seen';
  static const String wrong = 'wrong';
  static const String unwrong = 'unwrong';
  static const String master = 'master';
  static const String unmaster = 'unmaster';
  static const String rateAgain = 'rate_again';
  static const String rateHard = 'rate_hard';
  static const String rateGood = 'rate_good';
}

class PoolFilter {
  static const String done = 'done';
  static const String todo = 'todo';
  static const String wrong = 'wrong';
  static const String starred = 'starred';
  static const String plan = 'plan';
  static const String mastered = 'mastered';
}

class QuizMode {
  static const String practice = 'practice';
  static const String recite = 'recite';
  static const String quick = 'quick';
  static const String test = 'test';
}

class FacetLevel {
  static const String bankGroup = 'bank_group';
  static const String bank = 'bank';
  static const String subjectDir = 'subject_dir';
  static const String system = 'system';
  static const String chapter = 'chapter';
  static const String qtype = 'qtype';
  static const List<String> all = <String>[
    bankGroup,
    bank,
    subjectDir,
    system,
    chapter,
    qtype,
  ];
}

// ---------- 账号 ----------

class User {
  final int id;
  final String username;
  final bool isAdmin;
  const User({required this.id, required this.username, required this.isAdmin});
  factory User.fromJson(Map<String, dynamic> j) => User(
        id: _i(j['id']),
        username: _s(j['username']),
        isAdmin: _b(j['is_admin']),
      );
}

class AuthResult {
  final String token;
  final User user;
  const AuthResult({required this.token, required this.user});
  factory AuthResult.fromJson(Map<String, dynamic> j) => AuthResult(
        token: _s(j['token']),
        user: User.fromJson(asMap(j['user'])),
      );
}

class VersionInfo {
  final int build;
  final String note;
  final String apkSha256;
  const VersionInfo(
      {required this.build, required this.note, this.apkSha256 = ''});
  factory VersionInfo.fromJson(Map<String, dynamic> j) => VersionInfo(
      build: _i(j['build']),
      note: _s(j['note']),
      apkSha256: _s(j['apk_sha256']));
}

// ---------- 内容 ----------

class ChapterBrief {
  final int id;
  final String subject;
  final String title;
  const ChapterBrief(
      {required this.id, required this.subject, required this.title});
  factory ChapterBrief.fromJson(Map<String, dynamic> j) => ChapterBrief(
        id: _i(j['id']),
        subject: _s(j['subject']),
        title: _s(j['title']),
      );
}

class QuestionChapterBrief {
  final String name;
  final int count;
  const QuestionChapterBrief({required this.name, required this.count});
  factory QuestionChapterBrief.fromJson(Map<String, dynamic> j) =>
      QuestionChapterBrief(name: _s(j['name']), count: _i(j['count']));
}

class QuestionSystemBrief {
  final String name;
  final List<QuestionChapterBrief> chapters;
  const QuestionSystemBrief({required this.name, required this.chapters});
  factory QuestionSystemBrief.fromJson(Map<String, dynamic> j) =>
      QuestionSystemBrief(
        name: _s(j['name']),
        chapters: asMapList(j['chapters'])
            .map(QuestionChapterBrief.fromJson)
            .toList(),
      );
}

class QuestionSubjectBrief {
  final String subjectDir;
  final List<QuestionSystemBrief> systems;
  const QuestionSubjectBrief({required this.subjectDir, required this.systems});
  factory QuestionSubjectBrief.fromJson(Map<String, dynamic> j) =>
      QuestionSubjectBrief(
        subjectDir: _s(j['subject_dir']),
        systems:
            asMapList(j['systems']).map(QuestionSystemBrief.fromJson).toList(),
      );
}

class ContentTree {
  final List<ChapterBrief> mindmaps;
  final List<ChapterBrief> notes;
  final List<QuestionSubjectBrief> questionTree;
  const ContentTree(
      {required this.mindmaps,
      required this.notes,
      required this.questionTree});
  factory ContentTree.fromJson(Map<String, dynamic> j) => ContentTree(
        mindmaps: asMapList(j['mindmaps']).map(ChapterBrief.fromJson).toList(),
        notes: asMapList(j['notes']).map(ChapterBrief.fromJson).toList(),
        questionTree: asMapList(j['question_tree'])
            .map(QuestionSubjectBrief.fromJson)
            .toList(),
      );
}

class ChapterDetail {
  final int id;
  final String title;
  final String subject;
  final String html;
  final Map<String, String> meta;
  final List<int> pages;
  final List<ContentCitation> citations;
  const ChapterDetail({
    required this.id,
    required this.title,
    required this.subject,
    required this.html,
    required this.meta,
    required this.pages,
    this.citations = const <ContentCitation>[],
  });
  factory ChapterDetail.fromJson(Map<String, dynamic> j) {
    final Map<String, String> meta = <String, String>{};
    asMap(j['meta']).forEach((String k, dynamic v) {
      meta[k] = v == null ? '' : v.toString();
    });
    return ChapterDetail(
      id: _i(j['id']),
      title: _s(j['title']),
      subject: _s(j['subject']),
      html: _s(j['html']),
      meta: meta,
      pages: _li(j['pages']),
      citations: asMapList(j['citations']).map(ContentCitation.fromJson).toList(),
    );
  }
}

class SearchHit {
  final String kind;
  final int id;
  final String title;
  final String snippet;
  final String state;
  final bool starred;
  const SearchHit({
    required this.kind,
    required this.id,
    required this.title,
    required this.snippet,
    required this.state,
    required this.starred,
  });
  factory SearchHit.fromJson(Map<String, dynamic> j) => SearchHit(
        kind: _s(j['kind']),
        id: _i(j['id']),
        title: _s(j['title']),
        snippet: _s(j['snippet']),
        state: _s(j['state']),
        starred: _b(j['starred']),
      );
}

// ---------- 背卡 ----------

class CardPartIndex {
  final String subject;
  final String part;
  final int count;
  const CardPartIndex(
      {required this.subject, required this.part, required this.count});
  factory CardPartIndex.fromJson(Map<String, dynamic> j) => CardPartIndex(
        subject: _s(j['subject']),
        part: _s(j['part']),
        count: _i(j['count']),
      );
}

class CardReference {
  final int id;
  final String term;
  final String subject;
  final String reason;
  const CardReference({
    required this.id,
    required this.term,
    required this.subject,
    required this.reason,
  });
  factory CardReference.fromJson(Map<String, dynamic> j) => CardReference(
        id: _i(j['id']),
        term: _s(j['term']),
        subject: _s(j['subject']),
        reason: _s(j['reason']),
      );
}

class Card {
  final int id;
  final String subject;
  final String part;
  final String section;
  final String term;
  final String termHtml;
  final String hint;
  final String bodyHtml;
  final String state;
  final bool starred;
  final List<CardReference> relatedCards;
  final List<ContentCitation> citations;
  const Card({
    required this.id,
    required this.subject,
    required this.part,
    required this.section,
    required this.term,
    required this.termHtml,
    required this.hint,
    required this.bodyHtml,
    required this.state,
    required this.starred,
    this.relatedCards = const <CardReference>[],
    this.citations = const <ContentCitation>[],
  });
  factory Card.fromJson(Map<String, dynamic> j) => Card(
        id: _i(j['id']),
        subject: _s(j['subject']),
        part: _s(j['part']),
        section: _s(j['section']),
        term: _s(j['term']),
        termHtml: _s(j['term_html']),
        hint: _s(j['hint']),
        bodyHtml: _s(j['body_html']),
        state: _s(j['state']),
        starred: _b(j['starred']),
        relatedCards: j['related_cards'] is List
            ? (j['related_cards'] as List)
                .map((dynamic v) => CardReference.fromJson(asMap(v)))
                .toList()
            : const <CardReference>[],
        citations: asMapList(j['citations']).map(ContentCitation.fromJson).toList(),
      );
}

class CardQuery {
  final String? subject;
  final String? part;
  final List<int>? ids;
  final int? planDay;
  final bool starred;
  final bool due;
  const CardQuery({
    this.subject,
    this.part,
    this.ids,
    this.planDay,
    this.starred = false,
    this.due = false,
  });
  Map<String, Object?> toQuery() => <String, Object?>{
        'subject': subject,
        'part': part,
        'ids': ids,
        'plan_day': planDay,
        'starred': starred,
        'due': due,
      };
}

class SourceQuestion {
  final int id;
  final String qid;
  final String system;
  final String stemHtml;
  final String answer;
  final String analysisHtml;
  const SourceQuestion({
    required this.id,
    required this.qid,
    required this.system,
    required this.stemHtml,
    required this.answer,
    required this.analysisHtml,
  });
  factory SourceQuestion.fromJson(Map<String, dynamic> j) => SourceQuestion(
        id: _i(j['id']),
        qid: _s(j['qid']),
        system: _s(j['system']),
        stemHtml: _s(j['stem_html']),
        answer: _s(j['answer']),
        analysisHtml: _s(j['analysis_html']),
      );
}

// ---------- 刷题 ----------

class QuizFilter {
  final String? bankGroup;
  final String? bank;
  final String? subjectDir;
  final String? system;
  final String? chapter;
  final String? qtype;
  const QuizFilter({
    this.bankGroup,
    this.bank,
    this.subjectDir,
    this.system,
    this.chapter,
    this.qtype,
  });

  bool get isEmpty =>
      (bankGroup ?? '').isEmpty &&
      (bank ?? '').isEmpty &&
      (subjectDir ?? '').isEmpty &&
      (system ?? '').isEmpty &&
      (chapter ?? '').isEmpty &&
      (qtype ?? '').isEmpty;

  /// level 取 FacetLevel 常量
  String? valueOf(String level) {
    switch (level) {
      case FacetLevel.bankGroup:
        return bankGroup;
      case FacetLevel.bank:
        return bank;
      case FacetLevel.subjectDir:
        return subjectDir;
      case FacetLevel.system:
        return system;
      case FacetLevel.chapter:
        return chapter;
      case FacetLevel.qtype:
        return qtype;
    }
    return null;
  }

  /// 返回设置/清除（value 为 null 或空串）某一级后的新过滤器
  QuizFilter withLevel(String level, String? value) {
    final String? v = (value == null || value.isEmpty) ? null : value;
    return QuizFilter(
      bankGroup: level == FacetLevel.bankGroup ? v : bankGroup,
      bank: level == FacetLevel.bank ? v : bank,
      subjectDir: level == FacetLevel.subjectDir ? v : subjectDir,
      system: level == FacetLevel.system ? v : system,
      chapter: level == FacetLevel.chapter ? v : chapter,
      qtype: level == FacetLevel.qtype ? v : qtype,
    );
  }

  Map<String, Object?> toQuery() => <String, Object?>{
        'bank_group': bankGroup,
        'bank': bank,
        'subject_dir': subjectDir,
        'system': system,
        'chapter': chapter,
        'qtype': qtype,
      };
}

class FacetCount {
  final int total;
  final int done;
  const FacetCount({required this.total, required this.done});
}

/// level -> 选项 -> (总数, 已做数)
class FacetProgress {
  final Map<String, Map<String, FacetCount>> levels;
  const FacetProgress(this.levels);

  Map<String, FacetCount> of(String level) =>
      levels[level] ?? <String, FacetCount>{};

  factory FacetProgress.fromJson(Map<String, dynamic> j) {
    final Map<String, Map<String, FacetCount>> out =
        <String, Map<String, FacetCount>>{};
    for (final String level in FacetLevel.all) {
      final Map<String, FacetCount> m = <String, FacetCount>{};
      asMap(j[level]).forEach((String k, dynamic v) {
        final List<dynamic> p = v is List ? v : const <dynamic>[];
        m[k] = FacetCount(
          total: p.isNotEmpty ? _i(p[0]) : 0,
          done: p.length > 1 ? _i(p[1]) : 0,
        );
      });
      out[level] = m;
    }
    return FacetProgress(out);
  }
}

class QuizQuery {
  final QuizFilter filter;
  final List<int>? ids;
  final int? planDay;
  final bool starred;
  final bool wrong;
  final bool due;
  final bool random;
  final bool shuffle;
  final bool fresh;
  final int? limit;
  const QuizQuery({
    this.filter = const QuizFilter(),
    this.ids,
    this.planDay,
    this.starred = false,
    this.wrong = false,
    this.due = false,
    this.random = false,
    this.shuffle = false,
    this.fresh = false,
    this.limit,
  });
  Map<String, Object?> toQuery() => <String, Object?>{
        ...filter.toQuery(),
        'ids': ids,
        'plan_day': planDay,
        'starred': starred,
        'wrong': wrong,
        'due': due,
        'random': random,
        'shuffle': shuffle,
        'fresh': fresh,
        'limit': limit,
      };
}

class Question {
  final int id;
  final String qid;
  final String chapter;
  final String system;
  final String qtype;
  final String stemHtml;
  final String parentHtml;
  final String caseGroup;
  final int caseIndex;
  final int caseTotal;
  final List<String> optionsHtml;
  final List<String>? _optionLabels;
  List<String> get optionLabels => _optionLabels ?? sequentialOptionLabels(optionsHtml.length);
  final String answer;
  final String analysisHtml;
  final bool analysisEmpty;
  final List<String> tags;
  final String state;
  final bool starred;
  final bool done;
  final String lastPicked;
  final bool? lastCorrect;
  const Question({
    required this.id,
    required this.qid,
    required this.chapter,
    required this.system,
    required this.qtype,
    required this.stemHtml,
    required this.parentHtml,
    this.caseGroup = '',
    this.caseIndex = 0,
    this.caseTotal = 0,
    required this.optionsHtml,
    List<String>? optionLabels,
    required this.answer,
    required this.analysisHtml,
    required this.analysisEmpty,
    required this.tags,
    required this.state,
    required this.starred,
    required this.done,
    required this.lastPicked,
    required this.lastCorrect,
  }) : _optionLabels = optionLabels;
  factory Question.fromJson(Map<String, dynamic> j) => Question(
        id: _i(j['id']),
        qid: _s(j['qid']),
        chapter: _s(j['chapter']),
        system: _s(j['system']),
        qtype: _s(j['qtype']),
        stemHtml: _s(j['stem_html']),
        parentHtml: _s(j['parent_html']),
        caseGroup: _s(j['case_group']),
        caseIndex: _i(j['case_index']),
        caseTotal: _i(j['case_total']),
        optionsHtml: _ls(j['options_html']),
        optionLabels: readOptionLabels(j['option_labels'], _ls(j['options_html']).length),
        answer: _s(j['answer']),
        analysisHtml: _s(j['analysis_html']),
        analysisEmpty: _b(j['analysis_empty']),
        tags: _ls(j['tags']),
        state: _s(j['state']),
        starred: _b(j['starred']),
        done: _b(j['done']),
        lastPicked: _s(j['last_picked']),
        lastCorrect: _bn(j['last_correct']),
      );
}

class QuestionStat {
  final int total;
  final int correct;
  final Map<String, int> dist;
  const QuestionStat(
      {required this.total, required this.correct, required this.dist});
  factory QuestionStat.fromJson(Map<String, dynamic> j) {
    final Map<String, int> dist = <String, int>{};
    asMap(j['dist']).forEach((String k, dynamic v) {
      dist[k] = _i(v);
    });
    return QuestionStat(
        total: _i(j['total']), correct: _i(j['correct']), dist: dist);
  }
}

class RelatedCard {
  final int id;
  final String term;
  final String termHtml;
  final String hint;
  final String bodyHtml;
  const RelatedCard({
    required this.id,
    required this.term,
    required this.termHtml,
    required this.hint,
    required this.bodyHtml,
  });
  factory RelatedCard.fromJson(Map<String, dynamic> j) => RelatedCard(
        id: _i(j['id']),
        term: _s(j['term']),
        termHtml: _s(j['term_html']),
        hint: _s(j['hint']),
        bodyHtml: _s(j['body_html']),
      );
}

class RelatedQuestion {
  final int id;
  final String stem;
  final String label;
  final String reason;
  final bool inPlan;
  const RelatedQuestion({required this.id, required this.stem,
    required this.label, required this.reason, required this.inPlan});
  factory RelatedQuestion.fromJson(Map<String, dynamic> j) => RelatedQuestion(
    id: _i(j['id']), stem: _s(j['stem']), label: _s(j['label']),
    reason: _s(j['reason']), inPlan: _b(j['in_plan']),
  );
}

class QuestionFull {
  final int id;
  final String system;
  final String stemHtml;
  final List<String>? optionsHtml;
  final List<String>? optionLabels;
  final String answer;
  final String analysisHtml;
  final bool analysisEmpty;
  final List<RelatedCard> relatedCards;
  final QuestionStat stat;
  final List<String> tags;
  final String state;
  final bool starred;
  final List<ContentCitation> citations;
  const QuestionFull({
    required this.id,
    required this.system,
    required this.stemHtml,
    this.optionsHtml,
    this.optionLabels,
    required this.answer,
    required this.analysisHtml,
    required this.analysisEmpty,
    required this.relatedCards,
    required this.stat,
    required this.tags,
    required this.state,
    required this.starred,
    this.citations = const <ContentCitation>[],
  });
  factory QuestionFull.fromJson(Map<String, dynamic> j) => QuestionFull(
        id: _i(j['id']),
        system: _s(j['system']),
        stemHtml: _s(j['stem_html']),
        optionsHtml: j['options_html'] is List ? _ls(j['options_html']) : null,
        optionLabels: j['option_labels'] is List ? _ls(j['option_labels']) : null,
        answer: _s(j['answer']),
        analysisHtml: _s(j['analysis_html']),
        analysisEmpty: _b(j['analysis_empty']),
        relatedCards:
            asMapList(j['related_cards']).map(RelatedCard.fromJson).toList(),
        stat: QuestionStat.fromJson(asMap(j['stat'])),
        tags: _ls(j['tags']),
        state: _s(j['state']),
        starred: _b(j['starred']),
        citations: asMapList(j['citations']).map(ContentCitation.fromJson).toList(),
      );
}

class AttemptResult {
  /// 主观题无法判分时为 null
  final bool? correct;
  final String answer;
  final QuestionStat stat;
  const AttemptResult(
      {required this.correct, required this.answer, required this.stat});
  factory AttemptResult.fromJson(Map<String, dynamic> j) => AttemptResult(
        correct: _bn(j['correct']),
        answer: _s(j['answer']),
        stat: QuestionStat.fromJson(asMap(j['stat'])),
      );
}

class SubmitItem {
  final int questionId;
  final List<int> picked;
  const SubmitItem({required this.questionId, required this.picked});
  Map<String, dynamic> toJson() =>
      <String, dynamic>{'question_id': questionId, 'picked': picked};
}

class ChapterRate {
  final String chapter;
  final int total;
  final int correct;
  final double rate;
  const ChapterRate({
    required this.chapter,
    required this.total,
    required this.correct,
    required this.rate,
  });
  factory ChapterRate.fromJson(Map<String, dynamic> j) => ChapterRate(
        chapter: _s(j['chapter']),
        total: _i(j['total']),
        correct: _i(j['correct']),
        rate: _d(j['rate']),
      );
}

class ExamResultItem {
  final int questionId;
  final bool judged;
  final bool? correct;
  final String answer;
  const ExamResultItem({
    required this.questionId,
    required this.judged,
    required this.correct,
    required this.answer,
  });
  factory ExamResultItem.fromJson(Map<String, dynamic> j) => ExamResultItem(
        questionId: _i(j['question_id']),
        judged: _b(j['judged']),
        correct: _bn(j['correct']),
        answer: _s(j['answer']),
      );
}

class ExamReport {
  final int total;
  final int correct;
  final double score100;
  final double score300;
  final List<int> wrongIds;
  final List<ChapterRate> byChapter;
  final List<ExamResultItem> results;
  const ExamReport({
    required this.total,
    required this.correct,
    required this.score100,
    required this.score300,
    required this.wrongIds,
    required this.byChapter,
    required this.results,
  });
  factory ExamReport.fromJson(Map<String, dynamic> j) => ExamReport(
        total: _i(j['total']),
        correct: _i(j['correct']),
        score100: _d(j['score_100']),
        score300: _d(j['score_300']),
        wrongIds: _li(j['wrong_ids']),
        byChapter:
            asMapList(j['by_chapter']).map(ChapterRate.fromJson).toList(),
        results: asMapList(j['results']).map(ExamResultItem.fromJson).toList(),
      );
}

class PoolItem {
  final int id;
  final String qid;
  final String stem;
  final String answer;
  final String source;
  final List<String> tags;
  final String state;
  final bool starred;
  final bool inPlan;
  final bool done;
  final int attempts;
  final int wrongCount;
  final String? lastWrongAt;
  const PoolItem({
    required this.id,
    required this.qid,
    required this.stem,
    required this.answer,
    required this.source,
    required this.tags,
    required this.state,
    required this.starred,
    required this.inPlan,
    required this.done,
    required this.attempts,
    required this.wrongCount,
    required this.lastWrongAt,
  });
  factory PoolItem.fromJson(Map<String, dynamic> j) => PoolItem(
        id: _i(j['id']),
        qid: _s(j['qid']),
        stem: _s(j['stem']),
        answer: _s(j['answer']),
        source: _s(j['source']),
        tags: _ls(j['tags']),
        state: _s(j['state']),
        starred: _b(j['starred']),
        inPlan: _b(j['in_plan']),
        done: _b(j['done']),
        attempts: _i(j['attempts']),
        wrongCount: _i(j['wrong_count']),
        lastWrongAt: _sn(j['last_wrong_at']),
      );
}

class PoolStats {
  final int total;
  final int done;
  final int wrong;
  final int starred;
  final int plan;
  final int mastered;
  const PoolStats({
    required this.total,
    required this.done,
    required this.wrong,
    required this.starred,
    required this.plan,
    required this.mastered,
  });
  factory PoolStats.fromJson(Map<String, dynamic> j) => PoolStats(
        total: _i(j['total']),
        done: _i(j['done']),
        wrong: _i(j['wrong']),
        starred: _i(j['starred']),
        plan: _i(j['plan']),
        mastered: _i(j['mastered']),
      );
}

class PoolPage {
  final PoolStats stats;
  final List<PoolItem> items;
  const PoolPage({required this.stats, required this.items});
  factory PoolPage.fromJson(Map<String, dynamic> j) => PoolPage(
        stats: PoolStats.fromJson(asMap(j['stats'])),
        items: asMapList(j['items']).map(PoolItem.fromJson).toList(),
      );
}

class WrongBookGroup {
  final String chapter;
  final int count;
  final int wrongTotal;
  final String? lastWrongAt;
  const WrongBookGroup({
    required this.chapter,
    required this.count,
    required this.wrongTotal,
    required this.lastWrongAt,
  });
  factory WrongBookGroup.fromJson(Map<String, dynamic> j) => WrongBookGroup(
        chapter: _s(j['chapter']),
        count: _i(j['count']),
        wrongTotal: _i(j['wrong_total']),
        lastWrongAt: _sn(j['last_wrong_at']),
      );
}

class ExamRecord {
  final int id;
  final String createdAt;
  final String title;
  final int total;
  final int correct;
  final double rate;
  const ExamRecord({
    required this.id,
    required this.createdAt,
    required this.title,
    required this.total,
    required this.correct,
    required this.rate,
  });
  factory ExamRecord.fromJson(Map<String, dynamic> j) => ExamRecord(
        id: _i(j['id']),
        createdAt: _s(j['created_at']),
        title: _s(j['title']),
        total: _i(j['total']),
        correct: _i(j['correct']),
        rate: _d(j['rate']),
      );
}

// ---------- 今日 / 计划 / 统计 ----------

class UserPrefs {
  final int dailyGoal;
  final String? examDate;
  final int weakMinSamples;
  final double weakMaxRate;
  const UserPrefs({
    required this.dailyGoal,
    required this.examDate,
    required this.weakMinSamples,
    required this.weakMaxRate,
  });
  factory UserPrefs.fromJson(Map<String, dynamic> j) => UserPrefs(
        dailyGoal: _i(j['daily_goal']),
        examDate: _sn(j['exam_date']),
        weakMinSamples: _i(j['weak_min_samples']),
        weakMaxRate: _d(j['weak_max_rate']),
      );
}

class TodayCounts {
  final int due;
  final int wrong;
  final int starred;
  final int mastered;
  const TodayCounts({
    required this.due,
    required this.wrong,
    required this.starred,
    required this.mastered,
  });
  factory TodayCounts.fromJson(Map<String, dynamic> j) => TodayCounts(
        due: _i(j['due']),
        wrong: _i(j['wrong']),
        starred: _i(j['starred']),
        mastered: _i(j['mastered']),
      );
}

class TodaySummary {
  final int streak;
  final bool checkedIn;
  final int dailyGoal;
  final int doneToday;
  final int? examDaysLeft;
  final String? examDate;
  final TodayCounts counts;
  const TodaySummary({
    required this.streak,
    required this.checkedIn,
    required this.dailyGoal,
    required this.doneToday,
    required this.examDaysLeft,
    required this.examDate,
    required this.counts,
  });
  factory TodaySummary.fromJson(Map<String, dynamic> j) => TodaySummary(
        streak: _i(j['streak']),
        checkedIn: _b(j['checked_in']),
        dailyGoal: _i(j['daily_goal']),
        doneToday: _i(j['done_today']),
        examDaysLeft: _in(j['exam_days_left']),
        examDate: _sn(j['exam_date']),
        counts: TodayCounts.fromJson(asMap(j['counts'])),
      );
}

class CalendarMonth {
  final List<int> days;
  final int streak;
  const CalendarMonth({required this.days, required this.streak});
  factory CalendarMonth.fromJson(Map<String, dynamic> j) =>
      CalendarMonth(days: _li(j['days']), streak: _i(j['streak']));
}

class PlanItem {
  final String key;
  final String subject;
  final String part;
  final String label;
  final int cards;
  final int cardDone;
  final int questions;
  final int questionDone;
  final bool done;
  final int? day;
  const PlanItem({
    required this.key,
    required this.subject,
    required this.part,
    required this.label,
    required this.cards,
    required this.cardDone,
    required this.questions,
    required this.questionDone,
    required this.done,
    required this.day,
  });
  factory PlanItem.fromJson(Map<String, dynamic> j) => PlanItem(
        key: _s(j['key']),
        subject: _s(j['subject']),
        part: _s(j['part']),
        label: _s(j['label']),
        cards: _i(j['cards']),
        cardDone: _i(j['card_done']),
        questions: _i(j['questions']),
        questionDone: _i(j['question_done']),
        done: _b(j['done']),
        day: j['day'] == null ? null : _i(j['day']),
      );
}

class PlanToday {
  final bool configured;
  final String start;
  final int totalDays;
  final int dayNo;
  final int daysLeft;
  final int remaining;
  final bool finished;
  final int todayQuestions;
  final int todayCards;
  final int pendingQuestions;
  final int pendingCards;
  final List<int> scheduledDays;
  final List<PlanItem> todayItems;
  final List<PlanItem> items;
  const PlanToday({
    required this.configured,
    required this.start,
    required this.totalDays,
    required this.dayNo,
    required this.daysLeft,
    required this.remaining,
    required this.finished,
    this.todayQuestions = 0,
    this.todayCards = 0,
    this.pendingQuestions = 0,
    this.pendingCards = 0,
    this.scheduledDays = const <int>[],
    required this.todayItems,
    required this.items,
  });
  factory PlanToday.fromJson(Map<String, dynamic> j) => PlanToday(
        configured: _b(j['configured']),
        start: _s(j['start']),
        totalDays: _i(j['total_days']),
        dayNo: _i(j['day_no']),
        daysLeft: _i(j['days_left']),
        remaining: _i(j['remaining']),
        finished: _b(j['finished']),
        todayQuestions: _i(j['today_questions']),
        todayCards: _i(j['today_cards']),
        pendingQuestions: _i(j['pending_questions']),
        pendingCards: _i(j['pending_cards']),
        scheduledDays: _li(j['scheduled_days']),
        todayItems: asMapList(j['today_items']).map(PlanItem.fromJson).toList(),
        items: asMapList(j['items']).map(PlanItem.fromJson).toList(),
      );
}

class PlanOptionPart {
  final String part;
  final int cards;
  final int questions;
  const PlanOptionPart(
      {required this.part, required this.cards, required this.questions});
  factory PlanOptionPart.fromJson(Map<String, dynamic> j) => PlanOptionPart(
        part: _s(j['part']),
        cards: _i(j['cards']),
        questions: _i(j['questions']),
      );
}

class PlanOption {
  final String subject;
  final List<PlanOptionPart> parts;
  const PlanOption({required this.subject, required this.parts});
  factory PlanOption.fromJson(Map<String, dynamic> j) => PlanOption(
        subject: _s(j['subject']),
        parts: asMapList(j['parts']).map(PlanOptionPart.fromJson).toList(),
      );
}

class PlanDayCard {
  final int id;
  final String term;
  final String part;
  const PlanDayCard({required this.id, required this.term, required this.part});
  factory PlanDayCard.fromJson(Map<String, dynamic> j) => PlanDayCard(
        id: _i(j['id']),
        term: _s(j['term']),
        part: _s(j['part']),
      );
}

class PlanQuestionGroup {
  final String chapter;
  final List<int> ids;
  const PlanQuestionGroup({required this.chapter, required this.ids});
  factory PlanQuestionGroup.fromJson(Map<String, dynamic> j) =>
      PlanQuestionGroup(chapter: _s(j['chapter']), ids: _li(j['ids']));
}

class PlanDayDetail {
  final int no;
  final String title;
  final List<PlanDayCard> cards;
  final List<PlanQuestionGroup> questionGroups;
  const PlanDayDetail({
    required this.no,
    required this.title,
    required this.cards,
    required this.questionGroups,
  });
  factory PlanDayDetail.fromJson(Map<String, dynamic> j) => PlanDayDetail(
        no: _i(j['no']),
        title: _s(j['title']),
        cards: asMapList(j['cards']).map(PlanDayCard.fromJson).toList(),
        questionGroups: asMapList(j['question_groups'])
            .map(PlanQuestionGroup.fromJson)
            .toList(),
      );
}

class WeakSpot {
  final String system;
  final String chapter;
  final int total;
  final int correct;
  final double rate;
  final String? lastAttemptAt;
  const WeakSpot({
    required this.system,
    required this.chapter,
    required this.total,
    required this.correct,
    required this.rate,
    required this.lastAttemptAt,
  });
  factory WeakSpot.fromJson(Map<String, dynamic> j) => WeakSpot(
        system: _s(j['system']),
        chapter: _s(j['chapter']),
        total: _i(j['total']),
        correct: _i(j['correct']),
        rate: _d(j['rate']),
        lastAttemptAt: _sn(j['last_attempt_at']),
      );
}

class ScheduleItem {
  final int id;
  final String itemType;
  final int itemId;

  /// 'due' | 'weak'
  final String reason;
  final String title;
  final bool done;
  const ScheduleItem({
    required this.id,
    required this.itemType,
    required this.itemId,
    required this.reason,
    required this.title,
    required this.done,
  });
  factory ScheduleItem.fromJson(Map<String, dynamic> j) => ScheduleItem(
        id: _i(j['id']),
        itemType: _s(j['item_type']),
        itemId: _i(j['item_id']),
        reason: _s(j['reason']),
        title: _s(j['title']),
        done: _b(j['done']),
      );
}

class ScheduleToday {
  final String day;
  final int goal;
  final List<ScheduleItem> items;
  final int doneCount;
  const ScheduleToday({
    required this.day,
    required this.goal,
    required this.items,
    required this.doneCount,
  });
  factory ScheduleToday.fromJson(Map<String, dynamic> j) => ScheduleToday(
        day: _s(j['day']),
        goal: _i(j['goal']),
        items: asMapList(j['items']).map(ScheduleItem.fromJson).toList(),
        doneCount: _i(j['done_count']),
      );
}

class SystemStat {
  final String system;
  final int total;
  final int correct;
  final double rate;
  const SystemStat({
    required this.system,
    required this.total,
    required this.correct,
    required this.rate,
  });
  factory SystemStat.fromJson(Map<String, dynamic> j) => SystemStat(
        system: _s(j['system']),
        total: _i(j['total']),
        correct: _i(j['correct']),
        rate: _d(j['rate']),
      );
}

class DailyStat {
  final String day;
  final int count;
  final int correct;
  const DailyStat(
      {required this.day, required this.count, required this.correct});
  factory DailyStat.fromJson(Map<String, dynamic> j) => DailyStat(
        day: _s(j['day']),
        count: _i(j['count']),
        correct: _i(j['correct']),
      );
}

class StatsOverview {
  final int totalQuestions;
  final int totalCards;
  final int totalChapters;
  final int attempted;
  final double accuracy;
  final List<SystemStat> bySystem;
  final List<DailyStat> daily;
  const StatsOverview({
    required this.totalQuestions,
    required this.totalCards,
    required this.totalChapters,
    required this.attempted,
    required this.accuracy,
    required this.bySystem,
    required this.daily,
  });
  factory StatsOverview.fromJson(Map<String, dynamic> j) => StatsOverview(
        totalQuestions: _i(j['total_questions']),
        totalCards: _i(j['total_cards']),
        totalChapters: _i(j['total_chapters']),
        attempted: _i(j['attempted']),
        accuracy: _d(j['accuracy']),
        bySystem: asMapList(j['by_system']).map(SystemStat.fromJson).toList(),
        daily: asMapList(j['daily']).map(DailyStat.fromJson).toList(),
      );
}

// ---------- 笔记 / 评论 ----------

class Note {
  final int id;
  final String targetType;
  final int targetId;
  final String body;
  final bool isPublic;
  final String createdAt;
  final String? stemPreview;
  const Note({
    required this.id,
    required this.targetType,
    required this.targetId,
    required this.body,
    required this.isPublic,
    required this.createdAt,
    required this.stemPreview,
  });
  factory Note.fromJson(Map<String, dynamic> j) => Note(
        id: _i(j['id']),
        targetType: _s(j['target_type']),
        targetId: _i(j['target_id']),
        body: _s(j['body']),
        isPublic: _b(j['is_public']),
        createdAt: _s(j['created_at']),
        stemPreview: _sn(j['stem_preview']),
      );
}

class PublicNote {
  final int id;
  final String body;
  final String createdAt;
  final String username;
  final int likes;
  final bool liked;
  final bool mine;
  const PublicNote({
    required this.id,
    required this.body,
    required this.createdAt,
    required this.username,
    required this.likes,
    required this.liked,
    required this.mine,
  });
  factory PublicNote.fromJson(Map<String, dynamic> j) => PublicNote(
        id: _i(j['id']),
        body: _s(j['body']),
        createdAt: _s(j['created_at']),
        username: _s(j['username']),
        likes: _i(j['likes']),
        liked: _b(j['liked']),
        mine: _b(j['mine']),
      );
}

class NoteLikeResult {
  final int likes;
  final bool liked;
  const NoteLikeResult({required this.likes, required this.liked});
  factory NoteLikeResult.fromJson(Map<String, dynamic> j) =>
      NoteLikeResult(likes: _i(j['likes']), liked: _b(j['liked']));
}

// ---------- AI 陪学 ----------

class ChatQuizOption {
  final String key;
  final String html;
  const ChatQuizOption({required this.key, required this.html});
  factory ChatQuizOption.fromJson(Map<String, dynamic> j) =>
      ChatQuizOption(key: _s(j['key']), html: _s(j['html']));
}

class ChatQuiz {
  final String qid;
  final String system;
  final bool multi;
  final String stemHtml;
  final List<ChatQuizOption> options;
  const ChatQuiz({
    required this.qid,
    required this.system,
    required this.multi,
    required this.stemHtml,
    required this.options,
  });
  factory ChatQuiz.fromJson(Map<String, dynamic> j) => ChatQuiz(
        qid: _s(j['qid']),
        system: _s(j['system']),
        multi: _b(j['multi']),
        stemHtml: _s(j['stem_html']),
        options: asMapList(j['options']).map(ChatQuizOption.fromJson).toList(),
      );
}

class ChatMessage {
  /// 'user' | 'assistant'
  final String role;
  final String content;
  final String html;
  final String createdAt;
  const ChatMessage({
    required this.role,
    required this.content,
    required this.html,
    required this.createdAt,
  });
  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        role: _s(j['role']),
        content: _s(j['content']),
        html: _s(j['html']),
        createdAt: _s(j['created_at']),
      );
}

class ChatReply {
  final String reply;
  final String replyHtml;
  final List<ChatQuiz> quizzes;
  const ChatReply(
      {required this.reply, required this.replyHtml, required this.quizzes});
  factory ChatReply.fromJson(Map<String, dynamic> j) => ChatReply(
        reply: _s(j['reply']),
        replyHtml: _s(j['reply_html']),
        quizzes: asMapList(j['quizzes']).map(ChatQuiz.fromJson).toList(),
      );
}

class ChatAnswerResult {
  final bool correct;
  final String answer;
  final String qid;
  final String reply;
  final String replyHtml;
  const ChatAnswerResult({
    required this.correct,
    required this.answer,
    required this.qid,
    required this.reply,
    required this.replyHtml,
  });
  factory ChatAnswerResult.fromJson(Map<String, dynamic> j) => ChatAnswerResult(
        correct: _b(j['correct']),
        answer: _s(j['answer']),
        qid: _s(j['qid']),
        reply: _s(j['reply']),
        replyHtml: _s(j['reply_html']),
      );
}

class ChatSendBody {
  final String message;
  final String? context;

  /// dataURL
  final String? image;
  final String? fileName;

  /// base64
  final String? fileData;
  const ChatSendBody({
    required this.message,
    this.context,
    this.image,
    this.fileName,
    this.fileData,
  });
  Map<String, dynamic> toJson() {
    final Map<String, dynamic> m = <String, dynamic>{'message': message};
    if (context != null && context!.isNotEmpty) m['context'] = context;
    if (image != null && image!.isNotEmpty) m['image'] = image;
    if (fileData != null && fileData!.isNotEmpty) {
      m['file'] = <String, dynamic>{'name': fileName ?? '', 'data': fileData};
    }
    return m;
  }
}

// ---------- 管理员 ----------

class AdminQuestion {
  final int id;
  final String stem;
  final String system;
  final List<String> options;
  final List<String>? _optionLabels;
  List<String> get optionLabels => _optionLabels ?? sequentialOptionLabels(options.length);
  final String answer;
  final String analysis;
  final List<String> tags;
  const AdminQuestion({
    required this.id,
    required this.stem,
    required this.system,
    required this.options,
    List<String>? optionLabels,
    required this.answer,
    required this.analysis,
    required this.tags,
  }) : _optionLabels = optionLabels;
  factory AdminQuestion.fromJson(Map<String, dynamic> j) => AdminQuestion(
        id: _i(j['id']),
        stem: _s(j['stem']),
        system: _s(j['system']),
        options: _ls(j['options']),
        optionLabels: readOptionLabels(j['option_labels'], _ls(j['options']).length),
        answer: _s(j['answer']),
        analysis: _s(j['analysis']),
        tags: _ls(j['tags']),
      );
}

class AdminQuestionPatch {
  final String? stem;
  final String? system;
  final List<String>? options;
  final List<String>? optionLabels;
  final String? answer;
  final String? analysis;
  final List<String>? tags;
  const AdminQuestionPatch({this.stem, this.system, this.options, this.optionLabels, this.answer, this.analysis, this.tags});
  Map<String, dynamic> toJson() {
    final Map<String, dynamic> m = <String, dynamic>{};
    if (stem != null) m['stem'] = stem;
    if (system != null) m['system'] = system;
    if (options != null) m['options'] = options;
    if (optionLabels != null) m['option_labels'] = optionLabels;
    if (answer != null) m['answer'] = answer;
    if (analysis != null) m['analysis'] = analysis;
    if (tags != null) m['tags'] = tags;
    return m;
  }
}

class AdminCard {
  final int id;
  final String subject;
  final String part;
  final String section;
  final String term;
  final String hint;
  final String body;
  const AdminCard({
    required this.id,
    required this.subject,
    required this.part,
    required this.section,
    required this.term,
    required this.hint,
    required this.body,
  });
  factory AdminCard.fromJson(Map<String, dynamic> j) => AdminCard(
        id: _i(j['id']),
        subject: _s(j['subject']),
        part: _s(j['part']),
        section: _s(j['section']),
        term: _s(j['term']),
        hint: _s(j['hint']),
        body: _s(j['body']),
      );
}

class AdminCardPatch {
  final String? section;
  final String? term;
  final String? hint;
  final String? body;
  const AdminCardPatch({this.section, this.term, this.hint, this.body});
  Map<String, dynamic> toJson() {
    final Map<String, dynamic> m = <String, dynamic>{};
    if (section != null) m['section'] = section;
    if (term != null) m['term'] = term;
    if (hint != null) m['hint'] = hint;
    if (body != null) m['body'] = body;
    return m;
  }
}

class Invite {
  final String code;
  final int createdBy;
  final int? usedBy;
  final String? usedByUsername;
  final String? usedAt;
  final String? createdAt;
  const Invite(
      {required this.code,
      required this.createdBy,
      this.usedBy,
      this.usedByUsername,
      this.usedAt,
      this.createdAt});
  factory Invite.fromJson(Map<String, dynamic> j) => Invite(
        code: _s(j['code']),
        createdBy: _i(j['created_by']),
        usedBy: j['used_by'] is num ? _i(j['used_by']) : null,
        usedByUsername: j['used_by_username']?.toString(),
        usedAt: j['used_at']?.toString(),
        createdAt: j['created_at']?.toString(),
      );
}

class AdminUser {
  final int id;
  final String username;
  final bool isAdmin;
  final String? createdAt;
  final String? lastLoginAt;
  final String? inviteCode;
  const AdminUser(
      {required this.id,
      required this.username,
      required this.isAdmin,
      this.createdAt,
      this.lastLoginAt,
      this.inviteCode});
  factory AdminUser.fromJson(Map<String, dynamic> j) => AdminUser(
        id: _i(j['id']),
        username: _s(j['username']),
        isAdmin: j['is_admin'] == true,
        createdAt: j['created_at']?.toString(),
        lastLoginAt: j['last_login_at']?.toString(),
        inviteCode: j['invite_code']?.toString(),
      );
}
