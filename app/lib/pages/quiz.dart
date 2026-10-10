import 'dart:async';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api.dart';
import '../widgets.dart';
import 'notes.dart';

/// 刷题入口页：模式选择 + 四维筛选 → 进入题组
class QuizPage extends StatefulWidget {
  const QuizPage({super.key});
  @override
  State<QuizPage> createState() => _QuizState();
}

/// 刷题模式：练习=即判即看解析 背题=直接看答案 快刷=答对自动跳题 测试=答完统一判分
enum QMode { practice, recite, quick, test }

class _QuizState extends State<QuizPage> {
  /// prog[level][value] = [total, done]，各选项作答进度
  Map<String, Map<String, List<int>>> prog = {};
  // 级联筛选：题库系 → 来源题库 → 学科 → 系统 → 章节 → 题型
  String? bankgrp, bank, subjdir, system, chapter, qtype;
  QMode _mode = QMode.practice;
  bool _shuffle = false;
  static const _order = ['bankgrp', 'bank', 'subjdir', 'system', 'chapter', 'qtype'];
  // 数据未刷新的级别（禁用下拉，防止看到旧选项）
  final Set<String> _stale = {..._order};
  // 单调递增的请求代次，丢弃过期的响应
  int _loadSeq = 0;
  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((p) {
      if (mounted) setState(() {
        _mode = QMode.values[p.getInt('qmode') ?? 0];
        _shuffle = p.getBool('qshuf') ?? false;
      });
    });
    _load();
  }
  Future<void> _load() async {
    final seq = ++_loadSeq;
    final p = <String>[];
    if (bankgrp != null) p.add('bankgrp=${Uri.encodeComponent(bankgrp!)}');
    if (bank != null) p.add('bank=${Uri.encodeComponent(bank!)}');
    if (subjdir != null) p.add('subjdir=${Uri.encodeComponent(subjdir!)}');
    if (system != null) p.add('system=${Uri.encodeComponent(system!)}');
    if (chapter != null) p.add('chapter=${Uri.encodeComponent(chapter!)}');
    try {
      final f = await Api.get(
          '/api/facets_prog${p.isEmpty ? '' : '?${p.join('&')}'}',
          cache: false);
      if (mounted && seq == _loadSeq) {
        setState(() {
          prog = (f as Map).map((k, v) => MapEntry(k.toString(),
              (v as Map).map((k2, v2) =>
                  MapEntry(k2.toString(), List<int>.from(v2 as List)))));
          _stale.clear();
        });
      }
    } catch (_) {
      if (mounted && seq == _loadSeq) {
        setState(_stale.clear);
        toast(context, '筛选数据加载失败，请下拉或重新选择重试');
      }
    }
  }

  List<String> _opts(String level) => (prog[level] ?? {}).keys.toList();

  /// 变更某一级：清空其后各级、标记为待刷新，再重新拉级联选项
  void _set(String level, String? v) {
    setState(() {
      switch (level) {
        case 'bankgrp':
          bankgrp = v; bank = null; subjdir = null; system = null;
          chapter = null; break;
        case 'bank':
          bank = v; subjdir = null; system = null; chapter = null; break;
        case 'subjdir':
          subjdir = v; system = null; chapter = null; break;
        case 'system':
          system = v; chapter = null; break;
        case 'chapter': chapter = v; break;
        case 'qtype': qtype = v; break;
      }
      _stale.addAll(_order.sublist(_order.indexOf(level) + 1));
    });
    _load();
  }

  String get _query {
    final p = <String>[];
    if (subjdir != null) p.add('subjdir=${Uri.encodeComponent(subjdir!)}');
    if (system != null) p.add('system=${Uri.encodeComponent(system!)}');
    if (qtype != null) p.add('qtype=${Uri.encodeComponent(qtype!)}');
    if (bank != null) p.add('bank=${Uri.encodeComponent(bank!)}');
    if (bankgrp != null) p.add('bankgrp=${Uri.encodeComponent(bankgrp!)}');
    if (chapter != null) p.add('chapter=${Uri.encodeComponent(chapter!)}');
    if (_shuffle) p.add('shuffle=1');
    return p.join('&');
  }

  static const _modes = [
    (QMode.practice, '✍️ 练习'),
    (QMode.recite, '📖 背题'),
    (QMode.quick, '⚡ 快刷'),
    (QMode.test, '📋 测试'),
  ];

  void _openRun({String? extra}) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => QuizListPage(
        query: extra ?? (_query + '&limit=5000'), mode: _mode)));
  }

  Future<void> _startMock() async {
    try {
      final m = await Api.get('/api/mock?n=180', cache: false);
      final ids = (m['ids'] as List).cast<int>();
      if (ids.isEmpty) { if (mounted) toast(context, '题库可判分题不足'); return; }
      if (mounted) {
        Navigator.push(context, MaterialPageRoute(builder: (_) => QuizListPage(
            ids: ids, mode: QMode.test,
            examTitle: '全真模考', examMins: 180)));
      }
    } catch (_) { if (mounted) toast(context, '组卷失败'); }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('刷题')),
      body: ListView(padding: const EdgeInsets.all(14), children: [
        // 模式选择（医考帮式四种）
        Wrap(spacing: 8, children: [
          for (final m in _modes)
            ChoiceChip(
              label: Text(m.$2),
              selected: _mode == m.$1,
              onSelected: (_) {
                setState(() => _mode = m.$1);
                SharedPreferences.getInstance()
                    .then((p) => p.setInt('qmode', m.$1.index));
              }),
        ]),
        Padding(padding: const EdgeInsets.only(top: 4, bottom: 6),
          child: Text(
            const {
              QMode.practice: '选完即判分看解析，错题自动入本',
              QMode.recite: '直接展开答案与解析，快速过题',
              QMode.quick: '答对自动跳下一题，高强度刷',
              QMode.test: '全部答完后交卷统一判分出报告',
            }[_mode]!,
            style: const TextStyle(fontSize: 11.5, color: Colors.grey))),
        _pick('题库系', bankgrp, 'bankgrp', (v) => _set('bankgrp', v)),
        _pick('来源题库', bank, 'bank', (v) => _set('bank', v)),
        _pick('学科', subjdir, 'subjdir', (v) => _set('subjdir', v),
            fmt: (s) => s.replaceAll(RegExp(r'^\d+-'), '')),
        _pick('系统', system, 'system', (v) => _set('system', v)),
        _pick('章节', chapter, 'chapter', (v) => _set('chapter', v),
            fmt: (s) => s.split('·').last.trim()),
        _pick('题型', qtype, 'qtype', (v) => _set('qtype', v)),
        Row(children: [
          Checkbox(value: _shuffle, onChanged: (v) {
            setState(() => _shuffle = v ?? false);
            SharedPreferences.getInstance()
                .then((p) => p.setBool('qshuf', _shuffle));
          }),
          const Text('乱序刷题', style: TextStyle(fontSize: 13)),
        ]),
        const SizedBox(height: 8),
        FilledButton.icon(
          icon: const Icon(Icons.list_alt),
          label: const Text('浏览题目清单'),
          onPressed: () => Navigator.push(context, MaterialPageRoute(
              builder: (_) => QListPage(query: _query))),
        ),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: FilledButton.tonalIcon(
            icon: const Icon(Icons.play_arrow),
            label: Text(_mode == QMode.test ? '开始测试' : '开始刷题'),
            onPressed: () => _openRun())),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(
            icon: const Icon(Icons.shuffle),
            label: const Text('随机120'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => QuizListPage(
                    query: _query + '&rand=1', mode: _mode))))),
        ]),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: OutlinedButton.icon(
            icon: const Icon(Icons.menu_book, size: 18),
            label: const Text('错题本'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => const WrongBookPage())))),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(
            icon: const Icon(Icons.school, size: 18),
            label: const Text('全真模考'),
            onPressed: _startMock)),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(
            icon: const Icon(Icons.trending_up, size: 18),
            label: const Text('成绩'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => const ExamsPage())))),
        ]),
      ]),
    );
  }

  Widget _pick(String label, String? val, String level,
      ValueChanged<String?> onChg, {String Function(String)? fmt}) {
    final counts = prog[level] ?? {};
    final stale = _stale.contains(level);
    final pri = Theme.of(context).colorScheme.primary;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: DropdownButtonFormField<String>(
        value: val, isExpanded: true,
        decoration: InputDecoration(labelText: label,
            border: const OutlineInputBorder(), isDense: true,
            suffixIcon: stale
                ? const Padding(padding: EdgeInsets.all(12),
                    child: SizedBox(width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2)))
                : null),
        items: [
          const DropdownMenuItem(value: null, child: Text('全部')),
          ...counts.keys.map((s) {
            final c = counts[s]!;
            final tot = c[0], done = c[1];
            final pct = tot > 0 ? (done * 100 / tot).round() : 0;
            return DropdownMenuItem(value: s,
                child: Row(children: [
                  Expanded(child: Text(fmt?.call(s) ?? s,
                      overflow: TextOverflow.ellipsis)),
                  Text(' $done/$tot · $pct%',
                      style: TextStyle(fontSize: 11,
                          color: done > 0 ? pri : Colors.grey)),
                ]));
          }),
        ],
        onChanged: stale ? null : onChg,
      ),
    );
  }
}

/// Q号跳转：立即 push 加载页（页面自身负责取题+加载提示），避免等待期重复点击
void pushQuestionByQid(BuildContext context, String qid) {
  Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => QuizListPage(qidJump: qid)));
}

/// 题组运行页：PageView 左右滑动切题，按题号保留作答状态，解析按需加载
class QuizListPage extends StatefulWidget {
  final String query;
  final List<int>? ids;
  final int? plan;   // 学习计划第N天：服务端按课表取当日题集
  final String? chapter, subjdir, qidJump;
  final QMode mode;
  final String? examTitle;   // 测试/模考标题（交卷记入成绩）
  final int examMins;        // 限时分钟数，0=不限时
  const QuizListPage({super.key, this.query = '', this.ids,
      this.plan, this.chapter, this.subjdir, this.qidJump,
      this.mode = QMode.practice, this.examTitle, this.examMins = 0});
  @override
  State<QuizListPage> createState() => _QuizListState();
}

class _QuizListState extends State<QuizListPage> {
  List qs = [];
  int i = 0;
  bool loading = true;
  String? loadErr;                    // 加载失败信息（与「空题集」区分）
  bool _submitted = false;            // 测试模式已交卷（回看解析）
  bool _sending = false;              // 交卷请求进行中
  int _leftSec = 0;                   // 剩余秒数
  DateTime? _examEnd;                 // 交卷截止时刻（wall-clock，后台照走）
  Timer? _examTimer;
  final Map<int, Map> _stats = {};    // qid → {tot,ok,dist}
  final PageController _pc = PageController();
  ScaffoldMessengerState? _msn;      // 用于退出时清掉残留 SnackBar

  bool get _recite => widget.mode == QMode.recite;
  bool get _test => widget.mode == QMode.test && !_submitted;
  bool get _revealed => _recite || _submitted;
  // —— 按题号留存的作答状态（切题往返不丢）——
  final Map<int, Set<int>> picked = {};   // qid → 已选选项下标
  final Map<int, bool> judged = {};       // qid → 是否已判分
  final Map<int, Set<int>> wrongPick = {};// qid → 选错的下标
  final Map<int, Set<int>> missedOk = {}; // qid → 漏选的正确项
  // —— 解析缓存与预取 ——
  final Map<int, Map> full = {};          // qid → {analysis, answer, rel}
  final Set<int> fetching = {};
  final Set<int> _gening = {};            // qid → AI 补解析进行中

  String get _path {
    if (widget.qidJump != null) return '/api/quiz?qids=${widget.qidJump}&lite=1';
    if (widget.plan != null) return '/api/quiz?plan=${widget.plan}';
    if (widget.ids != null) return '/api/quiz?ids=${widget.ids!.join(',')}';
    var q = widget.query;
    if (widget.chapter != null) {
      q = 'chapter=${Uri.encodeComponent(widget.chapter!)}'
          '&subjdir=${Uri.encodeComponent(widget.subjdir!)}';
    }
    return '/api/quiz${q.isEmpty ? '?' : '?$q&'}lite=1';
  }

  @override
  void initState() { super.initState(); _load(); }

  // 续刷位置键：path 可能含上千个 qid，一律 hash 防止键爆炸
  String get _posKey => Api.prefKey('qpos', _path);

  Future<void> _load() async {
    try {
      qs = await Api.get(_path);
      loadErr = null;
    } catch (_) { qs = []; loadErr = '题目加载失败，请检查网络后重试'; }
    loading = false;
    if (mounted) setState(() {});
    if (qs.isNotEmpty) {
      _prefetch(0);
      _syncCtx();
      // 续刷：恢复上次停下的位置
      final p = await SharedPreferences.getInstance();
      final last = p.getInt(_posKey) ?? 0;
      // 恢复上次作答状态（做过的题直接显示答案，医考帮式留痕）
      if (widget.mode != QMode.test) {
        for (final q in qs) {
          final lp = (q['lpick'] ?? '').toString();
          if (lp.isEmpty) continue;
          final id = q['id'] as int;
          final sel = lp.split('')
              .map((c) => 'ABCDEFGHIJ'.indexOf(c))
              .where((x) => x >= 0).toSet();
          if (sel.isEmpty) continue;
          picked[id] = sel;
          judged[id] = true;
          final correct = _answerIdx(q);
          wrongPick[id] = sel.difference(correct);
          missedOk[id] = correct.difference(sel);
        }
      }
      if (last > 0 && last < qs.length && mounted) {
        _msn = ScaffoldMessenger.of(context);
        _msn!.showSnackBar(SnackBar(
          content: Text('上次做到第 ${last + 1} 题'),
          duration: const Duration(seconds: 4),
          action: SnackBarAction(label: '继续', onPressed: () {
            _pc.jumpToPage(last);
            setState(() => i = last);
          })));
      }
    }
    // 测试/模考倒计时：按 wall-clock 截止时刻计，退后台不暂停（全真口径）
    if (widget.mode == QMode.test && widget.examMins > 0) {
      _examEnd = DateTime.now().add(Duration(minutes: widget.examMins));
      _leftSec = widget.examMins * 60;
      _examTimer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) { t.cancel(); return; }
        final left = _examEnd!.difference(DateTime.now()).inSeconds;
        setState(() => _leftSec = left < 0 ? 0 : left);
        if (left <= 0) { t.cancel(); _submitTest(); }
      });
    }
    if (_recite) {
      for (final q in qs) { judged[q['id'] as int] = true; }
    }
  }

  void _savePos(int idx) {
    SharedPreferences.getInstance()
        .then((p) => p.setInt(_posKey, idx));
  }

  /// 把当前题目告知 AI 陪学上下文
  void _syncCtx() {
    if (qs.isEmpty || i >= qs.length) return;
    final q = qs[i];
    viewCtx.value = '题目#${q['qid'] ?? q['id'] ?? ''}'
        '（${q['system'] ?? q['chapter'] ?? ''}）'
        '${plainHtml(q['stem'] as String?, 300)}';
  }

  /// 预取当前及后续题目的解析（先让用户做题，后台加载解析/图）
  void _prefetch(int idx) {
    for (var k = idx; k < idx + 2 && k < qs.length; k++) {
      _ensureFull(qs[k]['id'] as int);
    }
  }

  Future<void> _ensureFull(int id) async {
    if (full.containsKey(id) || fetching.contains(id)) return;
    fetching.add(id);
    try {
      full[id] = await Api.get('/api/q_full?id=$id');
    } catch (_) {
      full[id] = {'_err': true};   // 失败也要落态，否则 UI 永远转圈
    }
    fetching.remove(id);
    if (mounted) setState(() {});
  }

  Map _q(int idx) => qs[idx];
  bool _judged(Map q) => judged[q['id']] == true;
  bool _isMulti(Map q) =>
      (q['answer'] ?? '').toString().length > 1 || q['qtype'] == '多选';
  List _options(Map q) => (q['options'] as List? ?? []);
  Set<int> _answerIdx(Map q) {
    const letters = 'ABCDEFGHIJ';
    final ans = (q['answer'] ?? '').toString().toUpperCase();
    final s = <int>{};
    for (var k = 0; k < letters.length; k++) {
      if (ans.contains(letters[k])) s.add(k);
    }
    return s;
  }

  /// 上报作答：服务端判分+写统计+进度（答错入错题本/答对移出）
  Future<void> _record(Map q, Set<int> sel) async {
    final id = q['id'] as int;
    try {
      final j = await Api.post('/api/attempt',
          {'id': id, 'pick': sel.toList()});
      if (j is Map && j['stat'] is Map) {
        _stats[id] = Map<String, dynamic>.from(j['stat'] as Map);
      }
      if (j is Map && j['ok'] == true && q['state'] == 'again') {
        q['state'] = '';   // 做对移出错题本
      }
      if (mounted) setState(() {});
    } catch (_) {
      if (mounted) toast(context, '作答记录失败（网络异常），成绩可能未保存');
    }
  }

  void _tap(Map q, int idx) {
    final id = q['id'] as int;
    if (_recite || _submitted) return;
    if (!_test && _judged(q)) return;   // 已判分锁定（测试模式除外，可改选）
    picked.putIfAbsent(id, () => <int>{});
    setState(() {
      if (_test) {
        if (_isMulti(q)) {
          picked[id]!.contains(idx)
              ? picked[id]!.remove(idx) : picked[id]!.add(idx);
        } else {
          picked[id]!
            ..clear()
            ..add(idx);       // 测试单选：替换选择
        }
      } else if (_isMulti(q)) {
        picked[id]!.contains(idx) ? picked[id]!.remove(idx) : picked[id]!.add(idx);
      } else {
        picked[id]!.add(idx);
        judged[id] = true;
        _ensureFull(id);
        final ok = _answerIdx(q).contains(idx);
        if (!ok) {
          wrongPick[id] = {idx};
          q['state'] = 'again';
          toast(context, '答错了，已加入错题本');
        }
        _record(q, {idx});
        if (widget.mode == QMode.quick && ok) {
          Future.delayed(const Duration(milliseconds: 450), () {
            if (mounted) _nav1();
          });
        }
      }
    });
  }

  void _nav1() => _nav(1);

  void _submit(Map q) {
    final id = q['id'] as int;
    final correct = _answerIdx(q);
    final sel = picked[id] ?? <int>{};
    wrongPick[id] = sel.difference(correct);
    missedOk[id] = correct.difference(sel);
    setState(() { judged[id] = true; _ensureFull(id); });
    _record(q, sel);
    if (wrongPick[id]!.isNotEmpty || missedOk[id]!.isNotEmpty) {
      q['state'] = 'again';
      toast(context, '答错了，已加入错题本');
    }
  }

  /// 测试/模考交卷：服务端批量判分 → 成绩单页
  Future<void> _submitTest() async {
    if (_submitted || _sending) return;
    _sending = true;
    final items = [for (final q in qs)
      {'id': q['id'], 'pick': (picked[q['id']] ?? const <int>{}).toList()}];
    try {
      final rep = await Api.post('/api/quiz_submit',
          {'items': items, 'title': widget.examTitle ?? '测试'}, secs: 120);
      _submitted = true;
      _examTimer?.cancel();
      for (final r in (rep['results'] as List? ?? [])) {
        if (r['judged'] == true) {
          final rid = r['id'] as int;
          judged[rid] = true;
          final q = qs.firstWhere((x) => x['id'] == rid,
              orElse: () => <String, dynamic>{});
          if (r['ok'] == false) {
            wrongPick[rid] = picked[rid] ?? <int>{};
            if (q.isNotEmpty) q['state'] = 'again';
          } else if (q.isNotEmpty && q['state'] == 'again') {
            q['state'] = '';
          }
        }
      }
      if (mounted) setState(() {});
      if (mounted) {
        Navigator.push(context, MaterialPageRoute(builder: (_) =>
            ExamReportPage(rep: rep)));
      }
    } catch (_) {
      if (mounted) toast(context, '交卷失败，请检查网络后重试');
    }
    _sending = false;
  }

  void _nav(int d) {
    final ni = (i + d).clamp(0, qs.length - 1);
    if (ni == i) return;
    _pc.animateToPage(ni, duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut);
  }

  void _openQref(String qid) => pushQuestionByQid(context, qid);

  /// 题号网格跳转：点顶栏 i/N 弹出，绿=已答 红=答错 蓝框=当前
  void _jumpSheet() {
    final cs = Theme.of(context).colorScheme;
    showModalBottomSheet(context: context, isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.6, minChildSize: 0.4, maxChildSize: 0.92,
        expand: false,
        builder: (ctx, sc) => Column(children: [
          Padding(padding: const EdgeInsets.all(10),
            child: Text('共 ${qs.length} 题 · 绿=已答 红=答错',
                style: const TextStyle(color: Colors.grey))),
          Expanded(child: GridView.builder(
            controller: sc,
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 6, mainAxisSpacing: 6, crossAxisSpacing: 6),
            itemCount: qs.length,
            itemBuilder: (ctx2, idx) {
              final id = _q(idx)['id'] as int;
              final wrong = (wrongPick[id] ?? const <int>{}).isNotEmpty;
              final done = judged[id] == true ||
                  (picked[id] ?? const <int>{}).isNotEmpty;
              final cur2 = idx == i;
              return Semantics(
                button: true,
                label: '第 ${idx + 1} 题${done ? wrong ? '，答错' : '，已答' : ''}',
                child: InkWell(
                onTap: () {
                  Navigator.pop(ctx2);
                  _pc.jumpToPage(idx);
                  setState(() => i = idx);
                  _prefetch(idx); _savePos(idx);
                },
                child: Container(
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: wrong ? Colors.red.withOpacity(.18)
                        : done ? Colors.green.withOpacity(.18)
                        : null,
                    border: Border.all(
                        color: cur2 ? cs.primary : Colors.grey.shade400,
                        width: cur2 ? 2 : 1),
                    borderRadius: BorderRadius.circular(8)),
                  child: Text('${idx + 1}',
                      style: TextStyle(fontSize: 13,
                          color: wrong ? Colors.red
                              : done ? Colors.green.shade800
                              : null)),
                )));
            })),
        ])));
  }

  @override
  void dispose() {
    _examTimer?.cancel();
    _msn?.hideCurrentSnackBar();   // 「上次做到第N题」不残留到其他页
    _pc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('刷题')),
        body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: const [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('正在从题库中抽取…', style: TextStyle(color: Colors.grey)),
        ])),
      );
    }
    if (qs.isEmpty) {
      if (loadErr != null) {
        return Scaffold(appBar: AppBar(title: const Text('刷题')),
            body: LoadError(msg: loadErr!, onRetry: () {
              setState(() => loading = true);
              _load();
            }));
      }
      return Scaffold(appBar: AppBar(title: const Text('刷题')),
          body: Center(child: Text(widget.qidJump != null
              ? '未找到题目 ${widget.qidJump}' : '没有匹配的题目')));
    }
    final cur = _q(i);
    final modeName = const {QMode.practice: '练习', QMode.recite: '背题',
        QMode.quick: '快刷', QMode.test: '测试'}[widget.mode];
    return Scaffold(
      appBar: AppBar(title: InkWell(
          onTap: _jumpSheet,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('${i + 1} / ${qs.length}'),
            const Icon(Icons.arrow_drop_down, size: 20),
            Text(' · $modeName', style: const TextStyle(
                fontSize: 12, color: Colors.grey)),
          ])),
        actions: [
          if (widget.mode == QMode.test && widget.examMins > 0 && !_submitted)
            Center(child: Padding(padding: const EdgeInsets.only(right: 4),
              child: Text('⏱ ${_leftSec ~/ 60}:${(_leftSec % 60).toString().padLeft(2, '0')}',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                      color: _leftSec < 300 ? Colors.red : null)))),
          if (widget.mode == QMode.test && !_submitted)
            TextButton(
              onPressed: () {
                final un = qs.where((q) =>
                    (picked[q['id']] ?? const <int>{}).isEmpty).length;
                showDialog(context: context, builder: (ctx) => AlertDialog(
                  title: const Text('交卷'),
                  content: Text(un > 0 ? '还有 $un 题未作答，确定交卷？' : '确定交卷判分？'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx),
                        child: const Text('再想想')),
                    FilledButton(onPressed: () {
                      Navigator.pop(ctx); _submitTest();
                    }, child: const Text('交卷')),
                  ]));
              },
              child: const Text('交卷',
                  style: TextStyle(fontWeight: FontWeight.w700))),
          IconButton(icon: const Icon(Icons.forum_outlined, size: 20),
              tooltip: '讨论区',
              onPressed: () => showModalBottomSheet(
                  context: context, isScrollControlled: true,
                  builder: (_) => CommentSheet(ref: cur['id'] as int))),
          if (Api.admin)
            IconButton(icon: const Icon(Icons.edit, size: 20),
                tooltip: '编辑题目',
                onPressed: () => showModalBottomSheet(
                    context: context, isScrollControlled: true,
                    builder: (_) => AdminEditSheet(qid: cur['id'] as int,
                        onSaved: (sys) {
                          setState(() {
                            cur['system'] = sys;
                            full.remove(cur['id']);
                            _ensureFull(cur['id'] as int);
                          });
                        }))),
          IconButton(icon: const Icon(Icons.edit_note),
              tooltip: '笔记',
              onPressed: () => showModalBottomSheet(
                  context: context, isScrollControlled: true,
                  builder: (_) => NoteSheet(ref: cur['id'] as int))),
          IconButton(icon: const Icon(Icons.format_size, size: 20),
              onPressed: () => showFontSheet(context)),
          IconButton(
            icon: Icon(cur['starred'] == 1 ? Icons.star : Icons.star_border,
                color: Colors.amber),
            onPressed: () async {
              try {
                await mark('q', cur['id'],
                    cur['starred'] == 1 ? 'unstar' : 'star');
              } catch (_) {
                if (context.mounted) toast(context, '操作失败，请检查网络');
                return;
              }
              setState(() => cur['starred'] = cur['starred'] == 1 ? 0 : 1);
              if (context.mounted) {
                toast(context, cur['starred'] == 1 ? '已收藏' : '已取消收藏');
              }
            }),
        ]),
      body: Column(children: [
        if (Api.lastFromCache) const CacheBanner(),
        Expanded(child: PageView.builder(
        controller: _pc,
        itemCount: qs.length,
        onPageChanged: (idx) {
          setState(() => i = idx); _prefetch(idx); _savePos(idx);
          _syncCtx();
          if (_recite) mark('q', _q(idx)['id'] as int, 'seen');
        },
        itemBuilder: (ctx, idx) => _qPage(_q(idx)),
        )),
      ]),
      bottomNavigationBar: SafeArea(child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 4, 14, 8),
        child: Row(children: [
          Expanded(child: OutlinedButton(
              onPressed: i > 0 ? () => _nav(-1) : null,
              child: const Text('← 上一题'))),
          const SizedBox(width: 10),
          Expanded(child: FilledButton(
              onPressed: i < qs.length - 1 ? () => _nav(1) : null,
              child: const Text('下一题 →'))),
        ]),
      )),
    );
  }

  Widget _qPage(Map q) {
    final id = q['id'] as int;
    final opts = _options(q);
    final correct = _answerIdx(q);
    final jd = _judged(q);
    final f = full[id];
    final tagList = (q['tags'] ?? '').toString()
        .split(RegExp(r'[,，]')).where((s) => s.isNotEmpty).toList();
    return ListView(padding: const EdgeInsets.all(14), children: [
      Wrap(spacing: 6, children: [
        if ((q['qtype'] ?? '').toString().isNotEmpty)
          Chip(label: Text(q['qtype'], style: const TextStyle(fontSize: 11)),
              visualDensity: VisualDensity.compact),
        if ((q['system'] ?? '').toString().isNotEmpty)
          Chip(label: Text(q['system'], style: const TextStyle(fontSize: 11)),
              visualDensity: VisualDensity.compact),
        if (_isMulti(q) && (q['qtype'] ?? '') != '多选')
          const Chip(label: Text('多选', style: TextStyle(fontSize: 11)),
              visualDensity: VisualDensity.compact),
        for (final t in tagList)
          Chip(label: Text(t, style: const TextStyle(
                  fontSize: 11, color: Color(0xFFDC2626))),
              backgroundColor: const Color(0x14DC2626),
              side: const BorderSide(color: Color(0x33DC2626)),
              visualDensity: VisualDensity.compact),
      ]),
      if ((q['parent'] ?? '').toString().length > 4)
        Card(color: Colors.amber.withOpacity(0.08),
          child: Padding(padding: const EdgeInsets.all(10),
              child: HtmlView(q['parent'], onQref: _openQref))),
      const SizedBox(height: 6),
      HtmlView(q['stem'] ?? '', onQref: _openQref),
      const SizedBox(height: 10),
      for (var k = 0; k < opts.length; k++) _optTile(q, k, opts[k], correct),
      if (_isMulti(q) && !jd && !_test)
        Padding(padding: const EdgeInsets.symmetric(vertical: 10),
          child: FilledButton(onPressed: () => _submit(q),
              child: const Text('提交答案'))),
      if (jd) ...[
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: const Color(0x1416A34A),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0x3316A34A))),
          child: Text('答案：${q['answer']}',
              style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
        // 已做过（恢复的上次作答）→ 可清除重做
        if (jd && (widget.mode == QMode.practice || widget.mode == QMode.quick)
            && !_submitted)
          Align(alignment: Alignment.centerRight,
            child: TextButton.icon(
              style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              icon: const Icon(Icons.refresh, size: 14),
              label: const Text('重做本题', style: TextStyle(fontSize: 12)),
              onPressed: () => setState(() {
                judged.remove(id); picked.remove(id);
                wrongPick.remove(id); missedOk.remove(id);
              }))),
        _statBox(id, correct),
        const SizedBox(height: 6),
        if (f != null && f['_err'] == true)
          Padding(padding: const EdgeInsets.symmetric(vertical: 8),
            child: LoadError(msg: '解析加载失败', onRetry: () {
              full.remove(id);
              _ensureFull(id);
              setState(() {});
            }))
        else if (f != null) ...[
          HtmlView((f['analysis'] ?? '').toString().isEmpty
              ? '（源平台未提供解析）' : f['analysis'],
              onQref: _openQref),
          if (f['ana_empty'] == true) ...[
            for (final c in (f['rel'] as List? ?? const []))
              _relCard(c as Map),
            _anaGenBtn(id),
          ],
        ]
        else
          const Padding(padding: EdgeInsets.symmetric(vertical: 18),
              child: Center(child: SizedBox(width: 22, height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2)))),
        _actionBar(q),
      ],
      const SizedBox(height: 60),
    ]);
  }

  /// 全站作答统计条：做过N人次 · 正确率 · 选项分布
  Widget _statBox(int id, Set<int> correct) {
    final fmap = full[id];
    final s = _stats[id] ?? (fmap != null && fmap['stat'] is Map
        ? Map<String, dynamic>.from(fmap['stat'] as Map) : null);
    if (s == null || (s['tot'] ?? 0) == 0) return const SizedBox.shrink();
    final tot = s['tot'] as int, ok = (s['ok'] ?? 0) as int;
    final rate = tot > 0 ? (ok * 100 / tot).round() : 0;
    final dist = (s['dist'] as Map? ?? {});
    final totP = dist.values.fold<int>(0, (a, b) => a + (b as int)) == 0
        ? 1 : dist.values.fold<int>(0, (a, b) => a + (b as int));
    final keys = dist.keys.map((e) => e.toString()).toList()..sort();
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(color: Colors.grey.withOpacity(0.07),
          borderRadius: BorderRadius.circular(9)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('📊 全站做过 $tot 人次 · 正确率 $rate%',
            style: TextStyle(fontSize: 12,
                color: rate >= 60 ? Colors.green.shade700 : Colors.red.shade400,
                fontWeight: FontWeight.w600)),
        if (dist.isNotEmpty) ...[
          const SizedBox(height: 5),
          ClipRRect(borderRadius: BorderRadius.circular(4),
            child: SizedBox(height: 10, child: Row(children: [
              for (final L in keys)
                Expanded(
                  flex: dist[L] as int,
                  child: Container(color: correct.contains(
                      'ABCDEFGHIJ'.indexOf(L))
                      ? const Color(0xFF16A34A) : const Color(0xFFDC2626)),
                ),
            ]))),
          Padding(padding: const EdgeInsets.only(top: 3),
            child: Text(keys.map((L) =>
                '$L ${((dist[L] as int) * 100 / totP).round()}%').join('  '),
                style: const TextStyle(fontSize: 10.5, color: Colors.grey))),
        ],
      ]),
    );
  }

  /// 空解析题的关联知识卡（源平台无解析时挂载）
  Widget _relCard(Map c) {
    final pri = Theme.of(context).colorScheme.primary;
    final hint = (c['hint'] ?? '').toString();
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
      decoration: BoxDecoration(
          color: pri.withOpacity(0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border(left: BorderSide(color: pri, width: 3))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('📚 ${c['term']}${hint.isNotEmpty ? '  ·  $hint' : ''}',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                color: pri)),
        const SizedBox(height: 4),
        HtmlView(c['body'] ?? '', onQref: _openQref),
      ]));
  }

  /// AI 按知识库补解析按钮：生成后写回库永久生效
  Widget _anaGenBtn(int id) => Padding(
      padding: const EdgeInsets.only(top: 12),
      child: OutlinedButton.icon(
          icon: const Icon(Icons.auto_awesome, size: 16),
          label: Text(_gening.contains(id) ? '生成中…' : 'AI 按知识库补解析'),
          onPressed: _gening.contains(id) ? null : () async {
            setState(() => _gening.add(id));
            try {
              final j = await Api.post('/api/qana_gen', {'id': id}, secs: 90);
              final ana = (j is Map) ? (j['analysis'] ?? '').toString() : '';
              if (ana.isNotEmpty) {
                full[id] = {...?full[id],
                    'analysis': ana, 'ana_empty': false};
              } else if (mounted) {
                toast(context, '生成失败：${(j is Map) ? (j['err'] ?? '') : '稍后再试'}');
              }
            } catch (_) {
              if (mounted) toast(context, '生成失败，稍后再试');
            } finally {
              if (mounted) setState(() => _gening.remove(id));
            }
          }));

  /// 判分后操作条：复习计划 / 错题本 / 完全掌握
  Widget _actionBar(Map q) {
    final id = q['id'] as int;
    final st = (q['state'] ?? '').toString();
    final inWrong = st == 'again';
    final mastered = st == 'mastered';
    Widget btn(String label, IconData ic, Color c, VoidCallback f) => Expanded(
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
            foregroundColor: c,
            side: BorderSide(color: c.withOpacity(0.5)),
            padding: const EdgeInsets.symmetric(vertical: 10)),
        onPressed: f,
        icon: Icon(ic, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 12)),
      ));
    Future<void> act(String rating, String newState, String msg) async {
      try {
        await mark('q', id, rating);
      } catch (_) {
        if (mounted) toast(context, '操作失败，请检查网络');
        return;   // 失败不改状态，避免「以为已加入错题本」的假象
      }
      setState(() => q['state'] = newState);
      if (mounted) toast(context, msg);
    }
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Row(children: [
        btn('复习计划', Icons.schedule, const Color(0xFF2B6CB0),
            () => act('plan', 'plan', '已加入复习计划，到期会提醒')),
        const SizedBox(width: 8),
        btn(inWrong ? '移出错题本' : '加入错题本',
            inWrong ? Icons.remove_circle_outline : Icons.add_circle_outline,
            const Color(0xFFDC2626),
            () => act(inWrong ? 'unwrong' : 'wrong', inWrong ? '' : 'again',
                inWrong ? '已移出错题本' : '已加入错题本')),
        const SizedBox(width: 8),
        btn(mastered ? '取消掌握' : '完全掌握',
            mastered ? Icons.check_circle : Icons.check_circle_outline,
            const Color(0xFF16A34A),
            () => act(mastered ? 'unmaster' : 'master',
                mastered ? '' : 'mastered',
                mastered ? '已取消，重新参与抽题' : '已掌握，随机抽题不再出现')),
      ]),
    );
  }

  Widget _optTile(Map q, int idx, String html, Set<int> correct) {
    final id = q['id'] as int;
    final sel = (picked[id] ?? const <int>{}).contains(idx);
    final jd = _judged(q);
    Color? bg, bc;
    if (jd) {
      if (_recite) {
        // 背题：正确项绿、其余无标记
        if (correct.contains(idx)) { bg = const Color(0x2216A34A); bc = const Color(0xFF16A34A); }
      } else {
        if (sel && correct.contains(idx)) { bg = const Color(0x2216A34A); bc = const Color(0xFF16A34A); }
        else if (sel) { bg = const Color(0x22DC2626); bc = const Color(0xFFDC2626); }
        else if (correct.contains(idx)) { bg = const Color(0x22F59E0B); bc = const Color(0xFFF59E0B); }
      }
    } else if (sel) { bg = const Color(0x222B6CB0); bc = const Color(0xFF2B6CB0); }
    // 判分后附该选项的全网选择率
    final fmap2 = full[id];
    final st = _stats[id] ?? (fmap2 != null && fmap2['stat'] is Map
        ? Map<String, dynamic>.from(fmap2['stat'] as Map) : null);
    String distTxt = '';
    if (jd && st != null) {
      final dist = (st['dist'] as Map? ?? {});
      final totP = dist.values.fold<int>(0, (a, b) => a + (b as int));
      final me = dist['ABCDEFGHIJ'[idx]] as int? ?? 0;
      if (totP > 0) distTxt = ' · ${(me * 100 / totP).round()}%';
    }
    // 读屏语义：选项字母+内容+选中态+判分结果
    final letter = 'ABCDEFGHIJ'[idx];
    final multi = _isMulti(q);
    final tappable = !_recite && !_submitted && (_test || !jd);
    final semLabel = StringBuffer('选项 $letter。${plainHtml(html, 80)}');
    if (sel) semLabel.write('。已选中');
    if (jd) {
      if (correct.contains(idx)) semLabel.write('。正确选项');
      if (sel && !correct.contains(idx)) semLabel.write('。你的选择，答错');
      if (!sel && correct.contains(idx) && !_recite) semLabel.write('。你漏选');
    }
    return Semantics(
      button: tappable,
      label: semLabel.toString(),
      selected: sel,
      checked: multi && sel,
      enabled: tappable,
      onTap: tappable ? () => _tap(q, idx) : null,
      child: GestureDetector(
      onTap: () => _tap(q, idx),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: bc ?? Colors.grey.shade300),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          Container(
            width: 24, height: 24,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: bc ?? Colors.grey.shade200,
            ),
            child: Text('ABCDEFGHIJ'[idx],
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                    color: bc != null ? Colors.white : Colors.black87)),
          ),
          const SizedBox(width: 10),
          Expanded(child: ExcludeSemantics(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              HtmlView(html),
              if (distTxt.isNotEmpty)
                Text(distTxt.trim(), style: const TextStyle(
                    fontSize: 10.5, color: Colors.grey)),
            ]))),
        ]),
      ),
    ));
  }
}

/// 管理员编辑弹层：改分类标签 / 解析正文 / 插图
class AdminEditSheet extends StatefulWidget {
  final int qid;
  final void Function(String system)? onSaved;
  const AdminEditSheet({super.key, required this.qid, this.onSaved});
  @override
  State<AdminEditSheet> createState() => _AdminEditState();
}

class _AdminEditState extends State<AdminEditSheet> {
  final _sys = TextEditingController();
  final _ana = TextEditingController();
  List<String> _systems = [];
  bool _loading = true, _saving = false, _loadOk = false;
  String _msg = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _msg = ''; });
    try {
      final q = await Api.get('/api/admin/q?id=${widget.qid}', cache: false);
      _sys.text = (q['system'] ?? '').toString();
      _ana.text = (q['analysis'] ?? '').toString();
      _loadOk = true;
    } catch (_) {
      _loadOk = false;
      _msg = '题目数据加载失败，已禁用保存';
    }
    try {
      final f = await Api.get('/api/facets');
      _systems = (f['system'] as List? ?? []).map((e) => e.toString()).toList();
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _pickImg() async {
    final x = await ImagePicker().pickImage(
        source: ImageSource.gallery, maxWidth: 1600);
    if (x == null) return;
    setState(() => _msg = '上传中…');
    final url = await Api.uploadImage(x.path);
    if (!mounted) return;
    if (url == null) {
      setState(() => _msg = '上传失败');
      return;
    }
    final sel = _ana.selection;
    final pos = sel.isValid ? sel.start : _ana.text.length;
    final ins = '\n![]($url)\n';
    _ana.text = _ana.text.substring(0, pos) + ins + _ana.text.substring(pos);
    _ana.selection = TextSelection.collapsed(offset: pos + ins.length);
    setState(() => _msg = '已插入 $url');
  }

  Future<void> _save() async {
    setState(() { _saving = true; _msg = ''; });
    try {
      final j = await Api.post('/api/admin/q',
          {'id': widget.qid, 'system': _sys.text.trim(), 'analysis': _ana.text});
      if (j['ok'] == true && mounted) {
        widget.onSaved?.call(_sys.text.trim());
        Navigator.pop(context);
        return;
      }
      if (mounted) setState(() => _msg = '保存失败：服务端拒绝');
    } catch (_) {
      if (mounted) setState(() => _msg = '保存失败：网络异常');
    }
    if (mounted) setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
          left: 16, right: 16, top: 18),
      child: _loading
          ? const SizedBox(height: 200,
              child: Center(child: CircularProgressIndicator()))
          : SingleChildScrollView(child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
              Text('✏️ 编辑题目 #${widget.qid}',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              const SizedBox(height: 12),
              Autocomplete<String>(
                initialValue: TextEditingValue(text: _sys.text),
                optionsBuilder: (v) => v.text.isEmpty
                    ? _systems
                    : _systems.where((s) => s.contains(v.text)),
                onSelected: (s) => _sys.text = s,
                fieldViewBuilder: (ctx, ctrl, node, _) {
                  ctrl.addListener(() => _sys.text = ctrl.text);
                  if (ctrl.text.isEmpty && _sys.text.isNotEmpty) {
                    ctrl.text = _sys.text;
                  }
                  return TextField(controller: ctrl, focusNode: node,
                      decoration: const InputDecoration(
                          labelText: '分类标签（system，可输入新值）',
                          border: OutlineInputBorder(), isDense: true));
                },
              ),
              const SizedBox(height: 12),
              TextField(controller: _ana, maxLines: 12, minLines: 6,
                  style: const TextStyle(fontSize: 13),
                  decoration: const InputDecoration(
                      labelText: '解析（markdown 原文）',
                      alignLabelWithHint: true,
                      border: OutlineInputBorder())),
              const SizedBox(height: 10),
              Row(children: [
                OutlinedButton.icon(
                    onPressed: _pickImg,
                    icon: const Icon(Icons.image, size: 18),
                    label: const Text('上传图片插入')),
                const SizedBox(width: 10),
                Expanded(child: Text(_msg,
                    style: TextStyle(fontSize: 12,
                        color: _loadOk ? Colors.grey
                            : Theme.of(context).colorScheme.error))),
              ]),
              const SizedBox(height: 10),
              Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                if (!_loadOk)
                  TextButton.icon(onPressed: _load,
                      icon: const Icon(Icons.refresh, size: 16),
                      label: const Text('重试加载')),
                const Spacer(),
                TextButton(onPressed: () => Navigator.pop(context),
                    child: const Text('取消')),
                const SizedBox(width: 8),
                // 初始数据没读到时禁存——空表单覆盖会清空线上解析
                FilledButton(onPressed: (_saving || !_loadOk) ? null : _save,
                    child: Text(_saving ? '保存中…' : '保存')),
              ]),
              const SizedBox(height: 12),
            ])),
    );
  }
}
/// 题池清单页：分页浏览筛选结果，每题显示作答状态，支持多选后刷题
class QListPage extends StatefulWidget {
  final String query;
  const QListPage({super.key, required this.query});
  @override
  State<QListPage> createState() => _QListState();
}

class _QListState extends State<QListPage> {
  static const _pageSize = 60;
  static const _flts = [
    ('', '全部'), ('todo', '未做'), ('done', '已做'),
    ('wrong', '错题'), ('starred', '收藏'), ('plan', '计划'), ('mastered', '掌握'),
  ];
  final List<Map> items = [];
  final ScrollController _sc = ScrollController();
  final Set<int> sel = {};
  Map stats = {};
  int total = 0;
  String flt = '';
  bool loading = false, hasMore = true, selectMode = false;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load(true);
    _sc.addListener(() {
      if (_sc.position.pixels > _sc.position.maxScrollExtent - 400) _load(false);
    });
  }

  @override
  void dispose() { _sc.dispose(); super.dispose(); }

  Future<void> _load(bool reset) async {
    if (loading || (!reset && !hasMore)) return;
    if (reset) { items.clear(); hasMore = true; sel.clear(); }
    setState(() => loading = true);
    try {
      final j = await Api.get(
          '/api/qlist?${widget.query}&flt=$flt'
          '&offset=${items.length}&size=$_pageSize', cache: false);
      stats = j['stats'] ?? {};
      total = stats['tot'] ?? 0;
      final it = (j['items'] as List).cast<Map>();
      items.addAll(it);
      if (it.length < _pageSize) hasMore = false;
      _err = null;
    } catch (_) {
      _err = '加载失败，请检查网络';
      hasMore = false;   // 不再无限触发重试请求；由重试按钮复位
    }
    if (mounted) setState(() => loading = false);
  }

  /// 状态徽标：错/掌握/计划/已做/收藏（可叠加）
  List<Widget> _chips(Map q) {
    final w = <Widget>[];
    void chip(String t, Color c) => w.add(Container(
        margin: const EdgeInsets.only(left: 4),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(
            color: c.withOpacity(.12), borderRadius: BorderRadius.circular(6)),
        child: Text(t, style: TextStyle(fontSize: 10, color: c))));
    final st = q['state'];
    if (st == 'again') chip('错', Colors.red);
    if (st == 'mastered') chip('掌握', Colors.blue);
    if (q['plan'] == true) chip('计划', Colors.purple);
    if (q['done'] == true && st != 'again' && st != 'mastered')
      chip('已做', Colors.green);
    if (q['starred'] == 1) chip('★', Colors.amber.shade800);
    if ((q['wcnt'] ?? 0) > 0) chip('错${q['wcnt']}次', Colors.deepOrange);
    if ((q['tags'] ?? '').toString().isNotEmpty)
      chip((q['tags'] as String).split(RegExp(r'[,，]')).first,
          Colors.red.shade300);
    return w;
  }

  void _startSel() {
    if (sel.isEmpty) return;
    Navigator.push(context, MaterialPageRoute(
        builder: (_) => QuizListPage(ids: sel.toList()..sort())));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('题目清单 · $total'),
        actions: [
          IconButton(
            icon: Icon(selectMode
                ? Icons.check_box : Icons.check_box_outline_blank),
            tooltip: '多选',
            onPressed: () => setState(() {
              selectMode = !selectMode;
              if (!selectMode) sel.clear();
            })),
          IconButton(icon: const Icon(Icons.play_arrow), tooltip: '顺序刷全部',
            onPressed: () {
              if (total > 5000) {
                toast(context, '题池 $total 题超过上限，先刷前 5000');
              }
              Navigator.push(context, MaterialPageRoute(builder: (_) =>
                  QuizListPage(query: '${widget.query}&limit=5000')));
            }),
        ]),
      body: Column(children: [
        // 统计条 + 状态过滤
        Padding(padding: const EdgeInsets.fromLTRB(10, 6, 10, 0),
          child: Text('已做 ${stats['done'] ?? 0} · 错 ${stats['wrong'] ?? 0}'
              ' · 收藏 ${stats['star'] ?? 0} · 计划 ${stats['plan'] ?? 0}'
              ' · 掌握 ${stats['mast'] ?? 0}',
              style: const TextStyle(fontSize: 12, color: Colors.grey))),
        SizedBox(height: 44, child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 8),
          children: [for (final f in _flts)
            Padding(padding: const EdgeInsets.symmetric(horizontal: 3),
              child: ChoiceChip(
                label: Text(f.$2, style: const TextStyle(fontSize: 12)),
                selected: flt == f.$1,
                onSelected: (_) => setState(() { flt = f.$1; _load(true); })))])),
        const Divider(height: 1),
        Expanded(child: items.isEmpty && _err != null && !loading
            ? LoadError(msg: _err!, onRetry: () {
                hasMore = true; _load(true); })
            : items.isEmpty && !loading && _err == null
            ? const Center(child: Text('没有匹配的题目',
                style: TextStyle(color: Colors.grey)))
            : ListView.builder(
          controller: _sc,
          itemCount: items.length + ((hasMore || _err != null) ? 1 : 0),
          itemBuilder: (ctx, i) {
            if (i >= items.length) {
              if (_err != null) {
                return Padding(padding: const EdgeInsets.all(16),
                  child: Center(child: OutlinedButton.icon(
                    icon: const Icon(Icons.refresh, size: 16),
                    label: Text('$_err · 点按重试'),
                    onPressed: () { hasMore = true; _load(false); })));
              }
              return const Padding(padding: EdgeInsets.all(16),
                  child: Center(child: CircularProgressIndicator()));
            }
            final q = items[i];
            final id = q['id'] as int;
            final done = q['done'] == true;
            final wrong = q['state'] == 'again';
            return ListTile(
              dense: true,
              onTap: () => selectMode
                  ? setState(() => sel.contains(id) ? sel.remove(id) : sel.add(id))
                  : pushQuestionByQid(context, q['qid'].toString()),
              leading: selectMode
                  ? Checkbox(value: sel.contains(id),
                      onChanged: (_) => setState(() =>
                          sel.contains(id) ? sel.remove(id) : sel.add(id)))
                  : CircleAvatar(radius: 13,
                      backgroundColor: done
                          ? (wrong ? Colors.red : Colors.green).withOpacity(.15)
                          : Colors.grey.withOpacity(.12),
                      child: Text('${i + 1}', style: TextStyle(fontSize: 11,
                          color: done
                              ? (wrong ? Colors.red : Colors.green.shade800)
                              : Colors.grey))),
              title: Text(plainHtml(q['stem'] as String?, 120), maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13.5)),
              subtitle: Row(children: [
                Text('#${q['qid']}${(q['ans'] ?? '').toString().isNotEmpty
                    ? ' · ${q['ans']}' : ''}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
                ..._chips(q),
              ]),
            );
          })),
      ]),
      bottomNavigationBar: selectMode ? SafeArea(child: Padding(
        padding: const EdgeInsets.all(10),
        child: FilledButton.icon(
          icon: const Icon(Icons.play_arrow),
          label: Text('刷选中 ${sel.length} 题'),
          onPressed: sel.isEmpty ? null : _startSel)),
      ) : null,
    );
  }
}

// ==================== 讨论区（公开评论 + 点赞） ====================
class CommentSheet extends StatefulWidget {
  final int ref;
  const CommentSheet({super.key, required this.ref});
  @override
  State<CommentSheet> createState() => _CommentSheetState();
}

class _CommentSheetState extends State<CommentSheet> {
  List items = [];
  bool loading = true, sending = false;
  String? _err;
  final c = TextEditingController();

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      items = await Api.get(
          '/api/note_pub?kind=q&ref=${widget.ref}', cache: false);
      _err = null;
    } catch (_) { items = []; _err = '加载失败'; }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _post() async {
    final t = c.text.trim();
    if (t.isEmpty || sending) return;
    setState(() => sending = true);
    try {
      await Api.post('/api/note', {'kind': 'q',
          'ref': widget.ref.toString(), 'body': t, 'public': 1});
      c.clear();
      await _load();
    } catch (_) {
      if (mounted) toast(context, '发表失败');
    }
    if (mounted) setState(() => sending = false);
  }

  Future<void> _like(Map it) async {
    try {
      final j = await Api.post('/api/note_like', {'id': it['id']});
      if (mounted) {
        setState(() {
          it['likes'] = j['likes'];
          it['liked'] = j['liked'];
        });
      }
    } catch (_) {
      if (mounted) toast(context, '点赞失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    final hint = Theme.of(context).colorScheme.outline;
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(child: Container(
        constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.75),
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 10),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            const Text('💬 讨论区',
                style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(width: 8),
            Text('口诀 · 技巧 · 勘误',
                style: TextStyle(fontSize: 11.5, color: hint)),
            const Spacer(),
            Text('${items.length} 条',
                style: TextStyle(fontSize: 12, color: hint)),
          ]),
          const SizedBox(height: 8),
          Flexible(child: loading
              ? const Padding(padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator()))
              : _err != null
                  ? Padding(padding: const EdgeInsets.all(24),
                      child: Center(child: Column(mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('$_err，请检查网络',
                              style: const TextStyle(color: Colors.grey)),
                          const SizedBox(height: 8),
                          OutlinedButton(onPressed: () {
                            setState(() => loading = true);
                            _load();
                          }, child: const Text('重试')),
                        ])))
              : items.isEmpty
                  ? Padding(padding: const EdgeInsets.all(24),
                      child: Text('还没有讨论，来分享第一条口诀/技巧吧',
                          style: TextStyle(color: hint)))
                  : ListView.builder(shrinkWrap: true,
                      itemCount: items.length,
                      itemBuilder: (ctx, k) {
                        final it = items[k] as Map;
                        final dt = DateTime.fromMillisecondsSinceEpoch(
                            ((it['updated'] ?? 0) * 1000).toInt());
                        return Container(
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                          decoration: BoxDecoration(
                            color: Colors.grey.withOpacity(0.06),
                            borderRadius: BorderRadius.circular(9)),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(children: [
                                Text(it['uname'] ?? '同学',
                                    style: const TextStyle(fontSize: 11.5,
                                        fontWeight: FontWeight.w600)),
                                const SizedBox(width: 6),
                                Text('${dt.month}/${dt.day}',
                                    style: TextStyle(
                                        fontSize: 10.5, color: hint)),
                                const Spacer(),
                                Semantics(
                                  button: true,
                                  label: '点赞，当前 ${it['likes'] ?? 0} 赞'
                                      '${it['liked'] == true ? '，已赞' : ''}',
                                  onTap: () => _like(it),
                                  child: GestureDetector(
                                  onTap: () => _like(it),
                                  child: Padding(
                                    padding: const EdgeInsets.all(4),
                                    child: Text(
                                      '${it['liked'] == true ? '❤️' : '👍'} ${it['likes'] ?? 0}',
                                      style: TextStyle(fontSize: 12,
                                          color: it['liked'] == true
                                              ? Colors.red : hint))),
                                )),
                              ]),
                              const SizedBox(height: 3),
                              Text((it['body'] ?? '').toString(),
                                  style: const TextStyle(
                                      fontSize: 13.5, height: 1.6)),
                            ]),
                        );
                      })),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: c,
              maxLength: 300, maxLines: 1,
              style: const TextStyle(fontSize: 13.5),
              decoration: const InputDecoration(
                  hintText: '分享口诀 / 解题技巧 / 勘误…',
                  counterText: '', isDense: true,
                  border: OutlineInputBorder()))),
            const SizedBox(width: 8),
            FilledButton(onPressed: sending ? null : _post,
                child: Text(sending ? '…' : '发表')),
          ]),
        ]))));
  }
}

// ==================== 交卷成绩单 ====================
class ExamReportPage extends StatelessWidget {
  final Map rep;
  const ExamReportPage({super.key, required this.rep});

  @override
  Widget build(BuildContext context) {
    final score = rep['score'] ?? 0;
    final ok = rep['ok'] ?? 0, tot = rep['tot'] ?? 0;
    final wrong = (rep['wrong'] as List? ?? []).cast<int>();
    final byCh = (rep['by_chapter'] as List? ?? []);
    return Scaffold(
      appBar: AppBar(title: const Text('📋 成绩单')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        Center(child: Text('$score',
            style: TextStyle(fontSize: 56, fontWeight: FontWeight.w800,
                color: score >= 60 ? Colors.green : Colors.red))),
        Center(child: Text(
            '答对 $ok/$tot 题${rep['score300'] != null && tot >= 100 ? ' · 西综估分 ${rep['score300']}/300' : ''}',
            style: const TextStyle(fontSize: 13, color: Colors.grey))),
        const SizedBox(height: 20),
        const Text('分章正确率', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        for (final c in byCh)
          Padding(padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(children: [
              SizedBox(width: 150, child: Text(
                  (c['chapter'] ?? '').toString().split('·').last.trim(),
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12.5))),
              Expanded(child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: (c['rate'] ?? 0) / 100, minHeight: 9,
                  backgroundColor: Colors.grey.withOpacity(0.15),
                  color: (c['rate'] ?? 0) >= 60 ? Colors.green : Colors.red))),
              const SizedBox(width: 8),
              SizedBox(width: 52, child: Text('${c['ok']}/${c['tot']}',
                  textAlign: TextAlign.right,
                  style: const TextStyle(fontSize: 12, color: Colors.grey))),
            ])),
        const SizedBox(height: 22),
        FilledButton.icon(
          icon: const Icon(Icons.menu_book),
          label: const Text('逐题查看解析'),
          onPressed: () => Navigator.pop(context)),
        if (wrong.isNotEmpty) ...[
          const SizedBox(height: 10),
          OutlinedButton.icon(
            icon: const Icon(Icons.replay),
            label: Text('只刷错题 ${wrong.length} 道'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => QuizListPage(ids: wrong)))),
        ],
      ]),
    );
  }
}

// ==================== 成绩记录 ====================
class ExamsPage extends StatefulWidget {
  const ExamsPage({super.key});
  @override
  State<ExamsPage> createState() => _ExamsState();
}

class _ExamsState extends State<ExamsPage> {
  List rows = []; bool loading = true; String? _err;
  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try { rows = await Api.get('/api/exams', cache: false); _err = null; }
    catch (_) { rows = []; _err = '成绩加载失败'; }
    if (mounted) setState(() => loading = false);
  }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('📈 成绩记录')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : _err != null
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => loading = true); _load(); })
          : rows.isEmpty
              ? const Center(child: Text('还没有交卷记录',
                  style: TextStyle(color: Colors.grey)))
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: rows.length,
                  itemBuilder: (ctx, k) {
                    final r = rows[k] as Map;
                    final dt = DateTime.fromMillisecondsSinceEpoch(
                        ((r['ts'] ?? 0) * 1000).toInt());
                    return Card(child: ListTile(
                      leading: CircleAvatar(
                        backgroundColor: (r['rate'] ?? 0) >= 60
                            ? Colors.green.withOpacity(.15)
                            : Colors.red.withOpacity(.15),
                        child: Text('${r['rate']}',
                            style: TextStyle(fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: (r['rate'] ?? 0) >= 60
                                    ? Colors.green : Colors.red))),
                      title: Text(r['title'] ?? '测试',
                          style: const TextStyle(fontSize: 14)),
                      subtitle: Text('${r['ok']}/${r['tot']} 题 · '
                          '${dt.month}/${dt.day} '
                          '${dt.hour.toString().padLeft(2, '0')}:'
                          '${dt.minute.toString().padLeft(2, '0')}',
                          style: const TextStyle(fontSize: 12)),
                    ));
                  }));
  }
}

// ==================== 错题本（按章节分组 + 错次） ====================
class WrongBookPage extends StatefulWidget {
  const WrongBookPage({super.key});
  @override
  State<WrongBookPage> createState() => _WrongBookState();
}

class _WrongBookState extends State<WrongBookPage> {
  List rows = []; bool loading = true; String? _err;
  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try { rows = await Api.get('/api/wrongbook', cache: false); _err = null; }
    catch (_) { rows = []; _err = '错题本加载失败'; }
    if (mounted) setState(() => loading = false);
  }

  String _wts(Map r) {
    final t = (r['wts'] ?? 0);
    if (t <= 0) return '';
    final dt = DateTime.fromMillisecondsSinceEpoch((t * 1000).toInt());
    return ' · 最近 ${dt.month}/${dt.day}';
  }

  @override
  Widget build(BuildContext context) {
    final tot = rows.fold<int>(0, (a, b) => a + ((b['n'] ?? 0) as int));
    return Scaffold(
      appBar: AppBar(title: Text('📕 错题本 · $tot 题')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : _err != null
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => loading = true); _load(); })
          : rows.isEmpty
              ? const Center(child: Text('没有错题，继续保持 🎉',
                  style: TextStyle(color: Colors.grey)))
              : ListView(padding: const EdgeInsets.all(12), children: [
                  OutlinedButton.icon(
                    icon: const Icon(Icons.replay),
                    label: Text('全部重刷 $tot 题'),
                    onPressed: () => Navigator.push(context, MaterialPageRoute(
                        builder: (_) => const QuizListPage(
                            query: 'wrong=1&limit=5000')))),
                  const SizedBox(height: 10),
                  for (final r in rows)
                    Card(child: ListTile(
                      dense: true,
                      title: Text((r['chapter'] ?? '未分类').toString()
                          .split('·').last.trim(),
                          style: const TextStyle(fontSize: 13.5)),
                      subtitle: Text('在错 ${r['n']} 题 · 累计错 ${r['wcnt']} 次'
                          '${_wts(r)}',
                          style: const TextStyle(fontSize: 11.5)),
                      trailing: const Icon(Icons.chevron_right, size: 18),
                      onTap: () => Navigator.push(context, MaterialPageRoute(
                          builder: (_) => QuizListPage(query:
                              'wrong=1&chapter=${Uri.encodeComponent(r['chapter'])}'))),
                    )),
                ]));
  }
}
