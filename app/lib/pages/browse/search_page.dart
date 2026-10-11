import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';

const List<String> _hot = <String>[
  '心力衰竭',
  '肺炎链球菌',
  '消化性溃疡',
  '糖尿病酮症',
  '急性胰腺炎',
  '酶的竞争性抑制',
];

String _plain(String t) => t
    .replaceAll(RegExp(r'<[^>]*>'), '')
    .replaceAll('&nbsp;', ' ')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim();

List<InlineSpan> _highlight(String text, String q, TextStyle hit) {
  final String t = _plain(text);
  final List<String> words =
      q.split(RegExp(r'\s+')).where((String w) => w.isNotEmpty).toList();
  if (words.isEmpty) return <InlineSpan>[TextSpan(text: t)];
  final RegExp re = RegExp(words.map(RegExp.escape).join('|'), caseSensitive: false);
  final List<InlineSpan> out = <InlineSpan>[];
  int last = 0;
  for (final RegExpMatch m in re.allMatches(t)) {
    if (m.end == m.start) continue;
    if (m.start > last) out.add(TextSpan(text: t.substring(last, m.start)));
    out.add(TextSpan(text: t.substring(m.start, m.end), style: hit));
    last = m.end;
  }
  if (last < t.length) out.add(TextSpan(text: t.substring(last)));
  return out;
}

class SearchPage extends StatefulWidget {
  final String initialQuery;
  const SearchPage({super.key, this.initialQuery = ''});

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  late final TextEditingController _ctrl =
      TextEditingController(text: widget.initialQuery);
  String _kind = '';
  String _q = '';
  List<SearchHit>? _hits;
  Object? _err;
  bool _loading = false;
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    if (widget.initialQuery.trim().isNotEmpty) {
      _q = widget.initialQuery.trim();
      _run();
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _run() async {
    final int my = ++_seq;
    final String q = _q;
    if (q.isEmpty) {
      setState(() {
        _hits = null;
        _err = null;
        _loading = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final List<SearchHit> r =
          await Endpoints.search(q, kind: _kind.isEmpty ? null : _kind);
      if (!mounted || my != _seq) return;
      setState(() {
        _hits = r;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || my != _seq) return;
      setState(() {
        _err = e;
        _hits = null;
        _loading = false;
      });
    }
  }

  void _submit(String v) {
    _q = v.trim();
    FocusScope.of(context).unfocus();
    _run();
  }

  void _open(SearchHit h) {
    if (h.kind == SearchKind.question) {
      openQuizRun(context, QuizRunArgs(ids: <int>[h.id]));
    } else if (h.kind == SearchKind.card) {
      openCardRun(context, CardRunArgs(ids: <int>[h.id]));
    } else {
      openChapter(context, h.id);
    }
  }

  Widget _kindBadge(String kind) {
    switch (kind) {
      case SearchKind.question:
        return const AppBadge('题目', tone: BadgeTone.info);
      case SearchKind.card:
        return const AppBadge('考点', tone: BadgeTone.warn);
      default:
        return const AppBadge('章节', tone: BadgeTone.primary);
    }
  }

  Widget _hitCard(SearchHit h) {
    final ThemeData t = Theme.of(context);
    final Color pri = t.colorScheme.primary;
    final TextStyle hl = TextStyle(
      color: pri,
      fontWeight: FontWeight.w700,
      backgroundColor: pri.withOpacity(0.14),
    );
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        onTap: () => _open(h),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _kindBadge(h.kind),
                const SizedBox(width: 8),
                Expanded(
                  child: RichText(
                    text: TextSpan(
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: t.colorScheme.onSurface,
                      ),
                      children: _highlight(h.title, _q, hl),
                    ),
                  ),
                ),
                if (h.state == ProgressState.mastered) ...<Widget>[
                  const SizedBox(width: 6),
                  const AppBadge('已掌握', tone: BadgeTone.good),
                ],
                if (h.state == ProgressState.again) ...<Widget>[
                  const SizedBox(width: 6),
                  const AppBadge('错题', tone: BadgeTone.bad),
                ],
                if (h.state == ProgressState.plan) ...<Widget>[
                  const SizedBox(width: 6),
                  const AppBadge('计划', tone: BadgeTone.info),
                ],
                if (h.starred) ...<Widget>[
                  const SizedBox(width: 6),
                  Icon(Icons.star, size: 18, color: AppColors.of(context).warn),
                ],
              ],
            ),
            if (h.snippet.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              RichText(
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                text: TextSpan(
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.6,
                    color: t.colorScheme.onSurfaceVariant,
                  ),
                  children: _highlight(h.snippet, _q, hl),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _guide() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: <Widget>[
        const SizedBox(height: 40),
        const EmptyState('输入关键词开始搜索', icon: Icons.search),
        const SizedBox(height: 16),
        Text('热门检索',
            style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _hot
              .map((String w) => ActionChip(
                    label: Text(w),
                    onPressed: () {
                      _ctrl.text = w;
                      _submit(w);
                    },
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _results() {
    if (_q.isEmpty) return _guide();
    if (_loading) return const LoadingView();
    final Object? err = _err;
    if (err != null) return LoadError(msg: errText(err), onRetry: _run);
    final List<SearchHit> hits = _hits ?? <SearchHit>[];
    if (hits.isEmpty) {
      return EmptyState('没有找到与「$_q」相关的内容', icon: Icons.search_off);
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text('共 ${hits.length} 条结果',
              style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ),
        ...hits.map(_hitCard),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('搜索')),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _ctrl,
              autofocus: widget.initialQuery.isEmpty,
              textInputAction: TextInputAction.search,
              onSubmitted: _submit,
              onChanged: (String _) => setState(() {}),
              decoration: InputDecoration(
                hintText: '输入关键词，如：心力衰竭',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                suffixIcon: _ctrl.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: '清除',
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          _ctrl.clear();
                          _submit('');
                        },
                      ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Segmented<String>(
              options: const <String, String>{
                '': '全部',
                SearchKind.question: '题目',
                SearchKind.card: '考点',
                SearchKind.chapter: '章节',
              },
              value: _kind,
              onChanged: (String k) {
                setState(() => _kind = k);
                _run();
              },
            ),
          ),
          Expanded(child: _results()),
        ],
      ),
    );
  }
}
