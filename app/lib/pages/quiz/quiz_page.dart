import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';

const String _kModeKey = 'quiz.mode';
const String _kMinsKey = 'quiz.mins';

const Map<String, String> _modeNames = <String, String>{
  QuizMode.practice: '练习',
  QuizMode.recite: '背题',
  QuizMode.quick: '快刷',
  QuizMode.test: '测试',
};

const Map<String, String> _modeDescs = <String, String>{
  QuizMode.practice: '点选即判，立刻看解析',
  QuizMode.recite: '直接显示答案与解析',
  QuizMode.quick: '答对自动下一题',
  QuizMode.test: '全部答完统一交卷',
};

const Map<String, String> _levelNames = <String, String>{
  FacetLevel.bankGroup: '题库系',
  FacetLevel.bank: '来源题库',
  FacetLevel.subjectDir: '学科',
  FacetLevel.system: '系统',
  FacetLevel.chapter: '章节',
  FacetLevel.qtype: '题型',
};

class QuizPage extends StatefulWidget {
  const QuizPage({super.key});

  @override
  State<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends State<QuizPage> {
  QuizFilter _filter = const QuizFilter();
  FacetProgress? _facets;
  Object? _err;
  bool _loading = true;
  int _gen = 0;
  String _mode = QuizMode.practice;
  final TextEditingController _mins = TextEditingController(text: '0');
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _restore();
    _fetch(initial: true);
  }

  @override
  void dispose() {
    _mins.dispose();
    super.dispose();
  }

  Future<void> _restore() async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    if (!mounted) return;
    final String? m = p.getString(_kModeKey);
    setState(() {
      if (m != null && _modeNames.containsKey(m)) _mode = m;
      _mins.text = '${p.getInt(_kMinsKey) ?? 0}';
    });
  }

  Future<void> _setMode(String m) async {
    setState(() => _mode = m);
    final SharedPreferences p = await SharedPreferences.getInstance();
    await p.setString(_kModeKey, m);
  }

  int get _minsNum => int.tryParse(_mins.text.trim()) ?? 0;

  Future<void> _fetch({bool initial = false}) async {
    final int gen = ++_gen;
    if (!initial) {
      setState(() {
        _loading = true;
        _err = null;
      });
    }
    try {
      final FacetProgress f = await Endpoints.facets(_filter);
      if (!mounted || gen != _gen) return;
      setState(() {
        _facets = f;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || gen != _gen) return;
      setState(() {
        _err = e;
        _loading = false;
      });
    }
  }

  void _choose(String level, String? value) {
    QuizFilter f = _filter.withLevel(level, value);
    final int at = FacetLevel.all.indexOf(level);
    for (int i = at + 1; i < FacetLevel.all.length; i++) {
      f = f.withLevel(FacetLevel.all[i], null);
    }
    setState(() => _filter = f);
    _fetch();
  }

  void _reset() {
    setState(() => _filter = const QuizFilter());
    _fetch();
  }

  Future<void> _run({bool shuffle = false, bool random = false}) async {
    final int mins = _minsNum.clamp(0, 600).toInt();
    final SharedPreferences p = await SharedPreferences.getInstance();
    await p.setInt(_kMinsKey, mins);
    if (!mounted) return;
    await openQuizRun(
      context,
      QuizRunArgs(
        filter: _filter,
        mode: _mode,
        mins: (_mode == QuizMode.test && mins > 0) ? mins : null,
        shuffle: shuffle,
        random: random,
      ),
    );
  }

  Future<void> _mock() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final List<int> ids = await Endpoints.mock(n: 180);
      if (!mounted) return;
      if (ids.isEmpty) {
        toast(context, '题库暂无可用题目');
      } else {
        await openQuizRun(
          context,
          QuizRunArgs(
              ids: ids, mode: QuizMode.test, title: '全真模考', mins: 180),
        );
      }
    } catch (e) {
      if (mounted) toast(context, errText(e));
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final FacetProgress? f = _facets;
    int total = 0;
    if (f != null) {
      for (final FacetCount v in f.of(FacetLevel.bankGroup).values) {
        total += v.total;
      }
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('刷题'),
        actions: <Widget>[
          if (f != null)
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Center(child: Text('题库共 $total 题')),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          _modeCard(context),
          const SizedBox(height: 12),
          _filterCard(context),
          const SizedBox(height: 12),
          _shortcuts(context),
        ],
      ),
    );
  }

  Widget _modeCard(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          const Text('刷题模式', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          Segmented<String>(
              options: _modeNames, value: _mode, onChanged: _setMode),
          const SizedBox(height: 8),
          Text(_modeDescs[_mode] ?? '',
              style: TextStyle(fontSize: 12, color: grey)),
          if (_mode == QuizMode.test) ...<Widget>[
            const SizedBox(height: 12),
            TextField(
              controller: _mins,
              keyboardType: TextInputType.number,
              inputFormatters: <TextInputFormatter>[
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(3),
              ],
              decoration: const InputDecoration(
                labelText: '限时（分钟）',
                helperText: '0 表示不限时',
                isDense: true,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _filterCard(BuildContext context) {
    final FacetProgress? f = _facets;
    final bool hasFilter = !_filter.isEmpty;
    final List<Widget> kids = <Widget>[
      Row(
        children: <Widget>[
          const Expanded(
              child: Text('选择范围',
                  style: TextStyle(fontWeight: FontWeight.w700))),
          if (hasFilter)
            TextButton(
                onPressed: _loading ? null : _reset,
                child: const Text('清除筛选')),
        ],
      ),
    ];
    if (_err != null && f == null) {
      kids.add(LoadError(msg: errText(_err!), onRetry: _fetch));
    } else {
      if (_err != null) {
        kids.add(Row(
          children: <Widget>[
            Expanded(child: Text(errText(_err!))),
            TextButton(onPressed: _fetch, child: const Text('重试')),
          ],
        ));
      }
      for (final String level in FacetLevel.all) {
        kids.add(const SizedBox(height: 10));
        kids.add(_facetDropdown(level, f));
      }
    }
    kids.add(const SizedBox(height: 14));
    kids.add(FilledButton(
      style: FilledButton.styleFrom(minimumSize: const Size(0, 48)),
      onPressed: _loading ? null : () => _run(),
      child: const Text('开始刷题'),
    ));
    kids.add(const SizedBox(height: 8));
    kids.add(Row(
      children: <Widget>[
        Expanded(
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48)),
            onPressed: _loading ? null : () => _run(shuffle: true),
            child: const Text('乱序刷题'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48)),
            onPressed: _loading ? null : () => _run(random: true),
            child: const Text('随机抽120'),
          ),
        ),
      ],
    ));
    kids.add(const SizedBox(height: 8));
    kids.add(OutlinedButton.icon(
      style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48)),
      onPressed: () => openQuizPool(context, _filter),
      icon: const Icon(Icons.checklist, size: 18),
      label: const Text('挑选题目'),
    ));
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: kids,
      ),
    );
  }

  Widget _facetDropdown(String level, FacetProgress? f) {
    final Map<String, FacetCount> opts =
        f == null ? <String, FacetCount>{} : f.of(level);
    int sumDone = 0;
    int sumTotal = 0;
    for (final FacetCount v in opts.values) {
      sumDone += v.done;
      sumTotal += v.total;
    }
    final String selRaw = _filter.valueOf(level) ?? '';
    final String sel = opts.containsKey(selRaw) ? selRaw : '';
    final List<DropdownMenuItem<String>> items = <DropdownMenuItem<String>>[
      DropdownMenuItem<String>(
        value: '',
        child: Text(opts.isEmpty ? '全部' : '全部（$sumDone/$sumTotal）',
            maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      ...opts.entries.map((MapEntry<String, FacetCount> e) =>
          DropdownMenuItem<String>(
            value: e.key,
            child: Text('${e.key}  ${e.value.done}/${e.value.total}',
                maxLines: 1, overflow: TextOverflow.ellipsis),
          )),
    ];
    final bool enabled = !_loading && opts.isNotEmpty;
    return InputDecorator(
      decoration: InputDecoration(
        labelText: _levelNames[level] ?? level,
        isDense: true,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          isExpanded: true,
          value: sel,
          items: items,
          onChanged: enabled ? (String? v) => _choose(level, v) : null,
        ),
      ),
    );
  }

  Widget _shortcuts(BuildContext context) {
    return Column(
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: _Shortcut(
                icon: Icons.emoji_events_outlined,
                title: '全真模考',
                desc: '180 题 · 限时 180 分钟',
                onTap: _busy ? null : _mock,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _Shortcut(
                icon: Icons.menu_book_outlined,
                title: '错题本',
                desc: '按章节回顾错题',
                onTap: () => openWrongBook(context),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: <Widget>[
            Expanded(
              child: _Shortcut(
                icon: Icons.bar_chart,
                title: '成绩记录',
                desc: '测试与模考成绩',
                onTap: () => openExams(context),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _Shortcut(
                icon: Icons.star_outline,
                title: '收藏题',
                desc: '集中复习收藏',
                onTap: () => openQuizRun(
                    context, QuizRunArgs(starred: true, mode: _mode)),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Shortcut extends StatelessWidget {
  final IconData icon;
  final String title;
  final String desc;
  final VoidCallback? onTap;
  const _Shortcut({
    required this.icon,
    required this.title,
    required this.desc,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return AppCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, color: onTap == null ? cs.outline : cs.primary),
          const SizedBox(height: 6),
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(desc,
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
        ],
      ),
    );
  }
}
