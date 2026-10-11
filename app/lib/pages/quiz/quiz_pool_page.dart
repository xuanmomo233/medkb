import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';

const int _kSize = 50;

class _ChipDef {
  final String flt;
  final String label;
  final int? count;
  const _ChipDef(this.flt, this.label, this.count);
}

class QuizPoolPage extends StatefulWidget {
  final QuizFilter filter;
  const QuizPoolPage(this.filter, {super.key});

  @override
  State<QuizPoolPage> createState() => _QuizPoolPageState();
}

class _QuizPoolPageState extends State<QuizPoolPage> {
  String _flt = '';
  PoolStats? _stats;
  List<PoolItem> _items = <PoolItem>[];
  bool _more = false;
  bool _loading = true;
  bool _busy = false;
  Object? _error;
  int _seq = 0;
  final Set<int> _sel = <int>{};

  @override
  void initState() {
    super.initState();
    _fetch(0, initial: true);
  }

  Future<void> _fetch(int offset, {bool initial = false}) async {
    if (_busy) return;
    _busy = true;
    final int n = ++_seq;
    if (!initial) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final PoolPage r = await Endpoints.pool(widget.filter,
          flt: _flt.isEmpty ? null : _flt, offset: offset, size: _kSize);
      if (!mounted || n != _seq) return;
      setState(() {
        _stats = r.stats;
        _items = offset == 0 ? r.items : <PoolItem>[..._items, ...r.items];
        _more = r.items.length == _kSize;
        _busy = false;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || n != _seq) return;
      setState(() {
        _error = e;
        _busy = false;
        _loading = false;
      });
    }
  }

  void _changeFlt(String f) {
    if (f == _flt) return;
    _seq++;
    _busy = false;
    setState(() {
      _items = <PoolItem>[];
      _sel.clear();
      _more = false;
      _flt = f;
    });
    _fetch(0);
  }

  void _toggle(int id) {
    setState(() {
      if (!_sel.remove(id)) _sel.add(id);
    });
  }

  bool get _allOn => _items.isNotEmpty && _items.every((PoolItem i) => _sel.contains(i.id));

  void _toggleAll() {
    setState(() {
      if (_allOn) {
        _sel.clear();
      } else {
        _sel.addAll(_items.map((PoolItem i) => i.id));
      }
    });
  }

  void _runSel() {
    final List<int> ids = _items
        .where((PoolItem i) => _sel.contains(i.id))
        .map((PoolItem i) => i.id)
        .toList();
    if (ids.isEmpty) return;
    openQuizRun(context, QuizRunArgs(ids: ids));
  }

  @override
  Widget build(BuildContext context) {
    final String sub = <String?>[
      widget.filter.bankGroup,
      widget.filter.bank,
      widget.filter.subjectDir,
      widget.filter.system,
      widget.filter.chapter,
      widget.filter.qtype,
    ].where((String? s) => (s ?? '').isNotEmpty).join(' / ');
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text('挑选题目'),
            Text(sub.isEmpty ? '全部题库' : sub,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w400,
                    color: Theme.of(context).colorScheme.onSurfaceVariant)),
          ],
        ),
      ),
      body: Column(
        children: <Widget>[
          _chips(),
          _bar(context),
          const Divider(height: 1),
          Expanded(child: _list(context)),
        ],
      ),
    );
  }

  Widget _chips() {
    final PoolStats? st = _stats;
    final List<_ChipDef> defs = <_ChipDef>[
      _ChipDef('', '总数', st?.total),
      _ChipDef(PoolFilter.done, '已做', st?.done),
      _ChipDef(PoolFilter.wrong, '错题', st?.wrong),
      _ChipDef(PoolFilter.starred, '收藏', st?.starred),
      _ChipDef(PoolFilter.plan, '计划', st?.plan),
      _ChipDef(PoolFilter.mastered, '掌握', st?.mastered),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: Row(
        children: defs
            .map((_ChipDef d) => Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text('${d.label} ${d.count ?? '–'}'),
                    selected: _flt == d.flt,
                    onSelected: (bool _) => _changeFlt(d.flt),
                  ),
                ))
            .toList(),
      ),
    );
  }

  Widget _bar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 0, 12, 4),
      child: Row(
        children: <Widget>[
          Checkbox(
            value: _allOn,
            onChanged: _items.isEmpty ? null : (bool? _) => _toggleAll(),
          ),
          Expanded(
            child: GestureDetector(
              onTap: _items.isEmpty ? null : _toggleAll,
              behavior: HitTestBehavior.opaque,
              child: Text('全选（已选 ${_sel.length}）'),
            ),
          ),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: _sel.isEmpty ? null : _runSel,
            child: const Text('刷选中题目'),
          ),
        ],
      ),
    );
  }

  Widget _list(BuildContext context) {
    final Object? err = _error;
    if (err != null && _items.isEmpty) {
      return LoadError(msg: errText(err), onRetry: () => _fetch(0));
    }
    if (_loading && _items.isEmpty) return const LoadingView();
    if (_items.isEmpty) return const EmptyState('没有符合条件的题目');
    return ListView.builder(
      itemCount: _items.length + 1,
      itemBuilder: (BuildContext c, int i) {
        if (i < _items.length) return _row(c, _items[i]);
        return _footer(err);
      },
    );
  }

  Widget _footer(Object? err) {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (err != null) {
      return Padding(
        padding: const EdgeInsets.all(12),
        child: LoadError(
            msg: errText(err), onRetry: () => _fetch(_items.length)),
      );
    }
    if (_more) {
      return Padding(
        padding: const EdgeInsets.all(12),
        child: OutlinedButton(
          style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48)),
          onPressed: () => _fetch(_items.length),
          child: const Text('加载更多'),
        ),
      );
    }
    return const SizedBox(height: 24);
  }

  Widget _row(BuildContext context, PoolItem it) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool on = _sel.contains(it.id);
    return InkWell(
      onTap: () => _toggle(it.id),
      child: Container(
        color: on ? cs.primary.withOpacity(0.08) : null,
        constraints: const BoxConstraints(minHeight: 56),
        padding: const EdgeInsets.fromLTRB(4, 6, 12, 6),
        child: Row(
          children: <Widget>[
            Checkbox(value: on, onChanged: (bool? _) => _toggle(it.id)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      Text(it.qid,
                          style: TextStyle(
                              fontSize: 12, color: cs.onSurfaceVariant)),
                      Text('答案 ${it.answer}',
                          style: const TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w700)),
                      if (it.state == ProgressState.again)
                        const AppBadge('错', tone: BadgeTone.bad),
                      if (it.state == ProgressState.mastered)
                        const AppBadge('掌握', tone: BadgeTone.good),
                      if (it.inPlan)
                        const AppBadge('计划', tone: BadgeTone.warn),
                      if (it.done) const AppBadge('已做', tone: BadgeTone.info),
                      if (it.starred)
                        const AppBadge('收藏', tone: BadgeTone.warn),
                      if (it.wrongCount > 0)
                        Text('错 ${it.wrongCount} 次',
                            style: TextStyle(fontSize: 12, color: cs.error)),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(plainHtml(it.stem, 200),
                      maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
