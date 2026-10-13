import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';

const String kLetters = 'ABCDEFGH';

final RegExp _letterRe = RegExp(r'^[A-H]+$');

bool isMultiQ(Question q) => q.answer.length > 1 && _letterRe.hasMatch(q.answer);

bool hasOptionsQ(Question q) =>
    q.optionsHtml.isNotEmpty && _letterRe.hasMatch(q.answer);

String sortLetters(String s) {
  final List<String> l = s.split('')..sort();
  return l.join();
}

List<int> lettersToIdx(String s) => s
    .split('')
    .map((String c) => kLetters.indexOf(c))
    .where((int i) => i >= 0)
    .toList();

enum RunStatus { loading, error, ready }

enum MarkKind { star, wrong, master, plan }

class Ans {
  final String picked;
  final bool judged;
  final bool? correct;
  const Ans(this.picked, this.judged, this.correct);
}

class MarkPatch {
  final String state;
  final bool starred;
  const MarkPatch(this.state, this.starred);
}

class QuizSession extends ChangeNotifier {
  final QuizRunArgs args;
  final void Function(String msg) notify;
  void Function(int index)? pageTo;
  void Function()? onTimeUp;

  QuizSession(this.args, this.notify);

  RunStatus status = RunStatus.loading;
  Object? error;
  List<Question> questions = <Question>[];
  int idx = 0;
  final Map<int, Ans> ans = <int, Ans>{};
  final Map<int, QuestionFull> full = <int, QuestionFull>{};
  final Set<int> fullErr = <int>{};
  final Set<int> _fullReq = <int>{};
  final Map<int, QuestionStat> stats = <int, QuestionStat>{};
  final Map<int, MarkPatch> patch = <int, MarkPatch>{};
  final Set<int> hidden = <int>{};
  final ValueNotifier<int?> remaining = ValueNotifier<int?>(null);
  bool aiBusy = false;
  bool submitting = false;
  int? resumeAt;

  int? _deadline;
  Timer? _ticker;
  Timer? _quickTimer;
  bool _disposed = false;
  bool _submitted = false;

  bool get isTest => args.mode == QuizMode.test;
  bool get isRecite => args.mode == QuizMode.recite;
  bool get trackPos => !isTest && !args.random && !args.shuffle;
  int? get _limit => (args.random && args.ids == null) ? 120 : null;
  String get title => (args.title ?? '').isEmpty ? '测试' : args.title!;

  String get _raw =>
      args.continueKey ?? buildQuery(args.toQuery(limit: _limit).toQuery());
  String get _posKey => Api.prefKey('qpos', _raw);
  String get _testKey => Api.prefKey('qtest', _raw);

  String _sig(List<Question> l) =>
      Api.prefKey('qsig', l.map((Question q) => q.id).join(','));

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  int get answeredCount => questions
      .where((Question q) => (ans[q.id]?.picked ?? '').isNotEmpty)
      .length;

  String stateOf(Question q) => patch[q.id]?.state ?? q.state;
  bool starredOf(Question q) => patch[q.id]?.starred ?? q.starred;
  QuestionStat? statOf(Question q) => stats[q.id] ?? full[q.id]?.stat;

  bool showFull(Question q) =>
      isRecite || (ans[q.id]?.judged ?? false) || !hasOptionsQ(q);

  Future<void> load() async {
    status = RunStatus.loading;
    error = null;
    _emit();
    try {
      final List<Question> list =
          await Endpoints.questions(args.toQuery(limit: _limit), lite: true);
      final SharedPreferences p = await SharedPreferences.getInstance();
      if (_disposed) return;
      ans.clear();
      int start = 0;
      int? resume;
      _deadline = null;
      if (isTest) {
        Map<String, dynamic> saved = <String, dynamic>{};
        final String? raw = p.getString(_testKey);
        if (raw != null) {
          try {
            saved = asMap(jsonDecode(raw));
          } catch (_) {
            saved = <String, dynamic>{};
          }
        }
        final bool ok = saved['sig'] == _sig(list);
        if (ok) {
          final Map<String, dynamic> picks = asMap(saved['picks']);
          for (final Question q in list) {
            final Object? v = picks['${q.id}'];
            if (v is String && v.isNotEmpty) ans[q.id] = Ans(v, false, null);
          }
          final Object? i = saved['idx'];
          if (i is num && list.isNotEmpty) {
            start = i.toInt().clamp(0, list.length - 1).toInt();
          }
          final Object? d = saved['deadline'];
          _deadline = d is num ? d.toInt() : null;
        } else {
          final int mins = args.mins ?? 0;
          if (mins > 0) {
            _deadline = DateTime.now().millisecondsSinceEpoch + mins * 60000;
          }
        }
      } else {
        if (!isRecite) {
          for (final Question q in list) {
            if (q.done && q.lastPicked.isNotEmpty) {
              ans[q.id] = Ans(q.lastPicked, true, q.lastCorrect);
            }
          }
        }
        if (trackPos) {
          final int pos = p.getInt(_posKey) ?? 0;
          if (pos > 0 && pos < list.length) resume = pos;
        }
      }
      questions = list;
      idx = start;
      resumeAt = resume;
      status = RunStatus.ready;
      _emit();
      _ensure();
      if (isTest) {
        unawaited(_saveTest());
        _startTicker();
      }
    } catch (e) {
      if (_disposed) return;
      error = e;
      status = RunStatus.error;
      _emit();
    }
  }

  void dismissResume() {
    resumeAt = null;
    _emit();
  }

  void onPage(int i) {
    if (i == idx) return;
    idx = i;
    _quickTimer?.cancel();
    _ensure();
    if (trackPos) unawaited(_savePos());
    if (isTest) unawaited(_saveTest());
    _emit();
  }

  Future<void> _savePos() async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    await p.setInt(_posKey, idx);
  }

  Future<void> _saveTest() async {
    if (!isTest || status != RunStatus.ready || _submitted) return;
    final Map<String, String> picks = <String, String>{};
    ans.forEach((int id, Ans a) {
      if (a.picked.isNotEmpty) picks['$id'] = a.picked;
    });
    final SharedPreferences p = await SharedPreferences.getInstance();
    await p.setString(
        _testKey,
        jsonEncode(<String, Object?>{
          'sig': _sig(questions),
          'picks': picks,
          'deadline': _deadline,
          'idx': idx,
        }));
  }

  void _ensure() {
    if (questions.isEmpty) return;
    final Question q = questions[idx];
    if (showFull(q)) unawaited(loadFull(q.id));
    if (!isTest) {
      for (int i = idx + 1; i <= idx + 2 && i < questions.length; i++) {
        unawaited(loadFull(questions[i].id));
      }
    }
  }

  Future<void> loadFull(int id) async {
    if (_fullReq.contains(id)) return;
    _fullReq.add(id);
    if (fullErr.remove(id)) _emit();
    try {
      final QuestionFull f = await Endpoints.questionFull(id);
      if (_disposed) return;
      full[id] = f;
    } catch (_) {
      _fullReq.remove(id);
      fullErr.add(id);
    }
    _emit();
  }

  Future<void> refreshFull(int id) async {
    try {
      final QuestionFull f = await Endpoints.questionFull(id, cache: false);
      if (_disposed) return;
      full[id] = f;
      fullErr.remove(id);
      stats[id] = f.stat;
      questions = questions.map((Question q) {
        if (q.id != id) return q;
        return Question(
          id: q.id,
          qid: q.qid,
          chapter: q.chapter,
          system: f.system,
          qtype: q.qtype,
          stemHtml: f.stemHtml,
          parentHtml: q.parentHtml,
          optionsHtml: q.optionsHtml,
          answer: q.answer,
          analysisHtml: f.analysisHtml,
          analysisEmpty: f.analysisEmpty,
          tags: f.tags,
          state: q.state,
          starred: q.starred,
          done: q.done,
          lastPicked: q.lastPicked,
          lastCorrect: q.lastCorrect,
        );
      }).toList();
    } catch (e) {
      if (!_disposed) notify(errText(e));
    }
    _emit();
  }

  void pick(Question q, String letter) {
    if (!hasOptionsQ(q) || isRecite) return;
    final Ans? cur = ans[q.id];
    if (cur != null && cur.judged) return;
    final bool multi = isMultiQ(q);
    final String old = cur?.picked ?? '';
    final String picked;
    if (multi) {
      picked = old.contains(letter)
          ? old.replaceFirst(letter, '')
          : sortLetters(old + letter);
    } else {
      picked = letter;
    }
    if (!multi && !isTest) {
      judge(q, picked);
      return;
    }
    if (picked.isEmpty) {
      ans.remove(q.id);
    } else {
      ans[q.id] = Ans(picked, false, null);
    }
    if (isTest) unawaited(_saveTest());
    _emit();
  }

  void confirmMulti(Question q) {
    final Ans? cur = ans[q.id];
    if (cur == null || cur.judged || isTest || cur.picked.isEmpty) return;
    judge(q, cur.picked);
  }

  void judge(Question q, String picked) {
    final bool correct = sortLetters(picked) == sortLetters(q.answer);
    ans[q.id] = Ans(picked, true, correct);
    _emit();
    _ensure();
    unawaited(_report(q, picked));
    if (args.mode == QuizMode.quick && correct) {
      final int at = idx;
      _quickTimer?.cancel();
      _quickTimer = Timer(const Duration(milliseconds: 600), () {
        if (_disposed || idx != at || at >= questions.length - 1) return;
        pageTo?.call(at + 1);
      });
    }
  }

  Future<void> _report(Question q, String picked) async {
    try {
      final AttemptResult r =
          await Endpoints.attempt(q.id, lettersToIdx(picked));
      if (_disposed) return;
      stats[q.id] = r.stat;
      _emit();
    } catch (_) {
      if (!_disposed) notify('作答记录保存失败，请检查网络');
    }
  }

  void redo(Question q) {
    _quickTimer?.cancel();
    ans.remove(q.id);
    _emit();
  }

  void toggleReveal(Question q) {
    if (!hidden.remove(q.id)) hidden.add(q.id);
    _emit();
  }

  Future<void> toggleMark(Question q, MarkKind kind) async {
    final String prevState = stateOf(q);
    final bool prevStar = starredOf(q);
    String nextState = prevState;
    bool nextStar = prevStar;
    final String action;
    if (kind == MarkKind.star) {
      action = prevStar ? MarkAction.unstar : MarkAction.star;
      nextStar = !prevStar;
    } else if (kind == MarkKind.wrong) {
      final bool on = prevState == ProgressState.again;
      action = on ? MarkAction.unwrong : MarkAction.wrong;
      nextState = on ? ProgressState.none : ProgressState.again;
    } else if (kind == MarkKind.master) {
      final bool on = prevState == ProgressState.mastered;
      action = on ? MarkAction.unmaster : MarkAction.master;
      nextState = on ? ProgressState.none : ProgressState.mastered;
    } else {
      final bool on = prevState == ProgressState.plan;
      action = on ? MarkAction.unplan : MarkAction.plan;
      nextState = on ? ProgressState.none : ProgressState.plan;
    }
    patch[q.id] = MarkPatch(nextState, nextStar);
    _emit();
    try {
      await Endpoints.mark(TargetType.question, q.id, action);
    } catch (_) {
      if (_disposed) return;
      patch[q.id] = MarkPatch(prevState, prevStar);
      _emit();
      notify('操作失败，已恢复');
    }
  }

  Future<void> genAnalysis(Question q) async {
    if (aiBusy) return;
    aiBusy = true;
    _emit();
    try {
      final String h = await Endpoints.aiAnalysis(q.id);
      if (_disposed) return;
      final QuestionFull? f = full[q.id];
      if (h.isEmpty) {
        notify('AI 未返回解析，请稍后重试');
      } else if (f != null) {
        full[q.id] = QuestionFull(
          id: f.id,
          system: f.system,
          stemHtml: f.stemHtml,
          answer: f.answer,
          analysisHtml: h,
          analysisEmpty: false,
          relatedCards: f.relatedCards,
          stat: f.stat,
          tags: f.tags,
          state: f.state,
          starred: f.starred,
        );
      }
    } catch (e) {
      if (!_disposed) notify(errText(e));
    }
    aiBusy = false;
    _emit();
  }

  void _startTicker() {
    _ticker?.cancel();
    if (_deadline == null) return;
    _tick();
    _ticker = Timer.periodic(const Duration(seconds: 1), (Timer _) => _tick());
  }

  void _tick() {
    final int? d = _deadline;
    if (d == null || _disposed) return;
    final int ms = d - DateTime.now().millisecondsSinceEpoch;
    final int sec = ms <= 0 ? 0 : (ms + 999) ~/ 1000;
    remaining.value = sec;
    if (sec == 0 && !_submitted) {
      _ticker?.cancel();
      onTimeUp?.call();
    }
  }

  Future<ExamReport?> submit() async {
    if (_submitted || submitting) return null;
    _submitted = true;
    submitting = true;
    _emit();
    try {
      final List<SubmitItem> items = questions
          .map((Question q) => SubmitItem(
              questionId: q.id, picked: lettersToIdx(ans[q.id]?.picked ?? '')))
          .toList();
      final ExamReport r = await Endpoints.submitExam(title, items);
      _ticker?.cancel();
      final SharedPreferences p = await SharedPreferences.getInstance();
      await p.remove(_testKey);
      return r;
    } catch (e) {
      _submitted = false;
      submitting = false;
      if (!_disposed) {
        notify(errText(e));
        _emit();
      }
      return null;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _ticker?.cancel();
    _quickTimer?.cancel();
    remaining.dispose();
    super.dispose();
  }
}
