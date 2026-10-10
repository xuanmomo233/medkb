import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets.dart';
import 'quiz.dart';
import 'notes.dart';

/// 背卡入口页：学科分组选卡包
class CardsPage extends StatefulWidget {
  const CardsPage({super.key});
  @override
  State<CardsPage> createState() => _CardsState();
}

class _CardsState extends State<CardsPage> {
  List idx = [];
  bool _loading = true;
  String? _err;
  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      idx = await Api.get('/api/kp_index');
      _err = null;
    } catch (_) { idx = []; _err = '卡包目录加载失败'; }
    _loading = false;
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final bySubj = <String, List>{};
    for (final r in idx) { bySubj.putIfAbsent(r['subj'], () => []).add(r); }
    return Scaffold(
      appBar: AppBar(title: const Text('考点背卡')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _err != null
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => _loading = true); _load(); })
          : idx.isEmpty
              ? const Center(child: Text('暂无卡包',
                  style: TextStyle(color: Colors.grey)))
          : ListView(children: [
              for (final e in bySubj.entries)
                ExpansionTile(
                  title: Text(e.key, style: const TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w600)),
                  subtitle: Text(
                      '${e.value.fold<int>(0, (a, b) => a + (b['n'] as int))} 张卡',
                      style: const TextStyle(fontSize: 12)),
                  children: e.value.map<Widget>((r) => ListTile(
                    dense: true,
                    title: Text('${r['label']} (${r['n']})',
                        style: const TextStyle(fontSize: 13)),
                    onTap: () => Navigator.push(context, MaterialPageRoute(
                        builder: (_) => CardRunPage(
                            subj: r['subj'], part: r['part']))),
                  )).toList()),
            ]),
    );
  }
}

/// 背卡运行页
class CardRunPage extends StatefulWidget {
  final String? subj, part;
  final List<int>? ids;
  final int? plan;   // 学习计划第N天：服务端按课表取当日卡集
  const CardRunPage({super.key, this.subj, this.part, this.ids, this.plan});
  @override
  State<CardRunPage> createState() => _CardRunState();
}

class _CardRunState extends State<CardRunPage> {
  List cards = [];
  int i = 0;
  bool _loading = true;
  String? _err;
  final PageController _pc = PageController();
  final Set<int> flipped = {};   // 每张卡独立记住翻面状态
  final Map<int, List?> _src = {};      // 卡id → 源题解析（null=加载中）
  final Set<int> _srcErr = {};          // 源题加载失败的卡（可重试）
  final Set<int> _srcOpen = {};         // 已展开解析的卡

  /// 卡号网格跳转：点顶栏 i/N 弹出
  void _jumpSheet() {
    final cs = Theme.of(context).colorScheme;
    showModalBottomSheet(context: context, isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.6, minChildSize: 0.4, maxChildSize: 0.92,
        expand: false,
        builder: (ctx, sc) => Column(children: [
          Padding(padding: const EdgeInsets.all(10),
            child: Text('共 ${cards.length} 卡 · 点数字跳转',
                style: const TextStyle(color: Colors.grey))),
          Expanded(child: GridView.builder(
            controller: sc,
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 6, mainAxisSpacing: 6, crossAxisSpacing: 6),
            itemCount: cards.length,
            itemBuilder: (ctx2, idx) => Semantics(
              button: true,
              label: '第 ${idx + 1} 张卡',
              child: InkWell(
              onTap: () {
                Navigator.pop(ctx2);
                _pc.jumpToPage(idx);
                setState(() => i = idx);
              },
              child: Container(
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  border: Border.all(
                      color: idx == i ? cs.primary : Colors.grey.shade400,
                      width: idx == i ? 2 : 1),
                  borderRadius: BorderRadius.circular(8)),
                child: Text('${idx + 1}',
                    style: TextStyle(fontSize: 13,
                        color: idx == i ? cs.primary : null)),
              ))),
          )),
        ])));
  }

  /// 拉取该卡源题解析（机制原理详解），最多12题
  Future<void> _loadSrc(Map c) async {
    final id = c['id'] as int;
    setState(() { _srcOpen.add(id); _src[id] = null; _srcErr.remove(id); });
    try {
      final qs = await Api.get('/api/card_src?id=$id', cache: false);
      _src[id] = (qs as List).cast<Map>();
    } catch (_) { _src[id] = []; _srcErr.add(id); }
    if (mounted) setState(() {});
  }

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    String p;
    if (widget.plan != null) {
      p = '/api/cards?plan=${widget.plan}';
    } else if (widget.ids != null) {
      p = '/api/cards?ids=${widget.ids!.join(',')}';
    } else {
      p = '/api/cards?subj=${Uri.encodeComponent(widget.subj ?? '')}'
          '&part=${Uri.encodeComponent(widget.part ?? '')}';
    }
    try { cards = await Api.get(p); _err = null; }
    catch (_) { cards = []; _err = '卡片加载失败，请检查网络'; }
    _loading = false;
    if (mounted) setState(() {});
    _syncCtx();
  }

  /// 把当前卡片告知 AI 陪学上下文
  void _syncCtx() {
    if (cards.isEmpty) return;
    final c = cards[i];
    viewCtx.value = '卡片「${c['term'] ?? ''}」'
        '（${c['subj'] ?? ''}·${c['part'] ?? ''}）'
        '背面：${plainHtml(c['body'] as String?, 400)}';
  }

  void _nav(int d) {
    final ni = (i + d).clamp(0, cards.length - 1);
    if (ni == i) return;
    _pc.animateToPage(ni, duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut);
  }

  @override
  void dispose() { _pc.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(appBar: AppBar(title: const Text('背卡')),
          body: const Center(child: CircularProgressIndicator()));
    }
    if (cards.isEmpty) {
      return Scaffold(appBar: AppBar(title: const Text('背卡')),
          body: _err != null
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => _loading = true); _load(); })
              : const Center(child: Text('该卡包没有卡片',
                  style: TextStyle(color: Colors.grey))));
    }
    final c = cards[i];
    return Scaffold(
      appBar: AppBar(title: InkWell(
        onTap: _jumpSheet,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text('${i + 1} / ${cards.length} · ${c['subj']}'),
          const Icon(Icons.arrow_drop_down, size: 20),
        ])),
        actions: [
          IconButton(icon: const Icon(Icons.edit_note),
              tooltip: '笔记',
              onPressed: () => showModalBottomSheet(
                  context: context, isScrollControlled: true,
                  builder: (_) => NoteSheet(ref: c['id'] as int, kind: 'k'))),
          IconButton(icon: const Icon(Icons.format_size, size: 20),
              onPressed: () => showFontSheet(context)),
          IconButton(
            icon: Icon(c['starred'] == 1 ? Icons.star : Icons.star_border,
                color: Colors.amber),
            onPressed: () async {
              try {
                await mark('k', c['id'],
                    c['starred'] == 1 ? 'unstar' : 'star');
              } catch (_) {
                if (context.mounted) toast(context, '操作失败，请检查网络');
                return;
              }
              setState(() => c['starred'] = c['starred'] == 1 ? 0 : 1);
              if (context.mounted) {
                toast(context, c['starred'] == 1 ? '已收藏' : '已取消收藏');
              }
            }),
        ]),
      body: Column(children: [
        if (Api.lastFromCache) const CacheBanner(),
        Expanded(child: PageView.builder(
          controller: _pc,
          itemCount: cards.length,
          onPageChanged: (idx) { setState(() => i = idx); _syncCtx(); },
          itemBuilder: (ctx, idx) => _cardPage(cards[idx]),
        )),
      ]),
      bottomNavigationBar: SafeArea(child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 4, 14, 8),
        child: Row(children: [
          Expanded(child: OutlinedButton(
              onPressed: i > 0 ? () => _nav(-1) : null,
              child: const Text('← 上一张'))),
          const SizedBox(width: 10),
          Expanded(child: FilledButton(
              onPressed: i < cards.length - 1 ? () => _nav(1) : null,
              child: const Text('下一张 →'))),
        ]),
      )),
    );
  }

  Widget _cardPage(Map c) {
    final flip = flipped.contains(c['id']);
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text(c['part'] ?? '', style: TextStyle(fontSize: 12,
          color: Theme.of(context).colorScheme.primary)),
      const SizedBox(height: 6),
      Text(c['term'] ?? '', style: const TextStyle(
          fontSize: 22, fontWeight: FontWeight.w800)),
      if ((c['hint'] ?? '').toString().isNotEmpty)
        Padding(padding: const EdgeInsets.only(top: 4),
          child: Text(c['hint'], style: TextStyle(fontSize: 12,
              color: Theme.of(context).colorScheme.outline))),
      const SizedBox(height: 16),
      if (!flip)
        OutlinedButton.icon(
          icon: const Icon(Icons.flip),
          label: const Text('点我翻面'),
          onPressed: () => setState(() => flipped.add(c['id'])))
      else ...[
        HtmlView(c['body'] ?? '',
            onQref: (qid) => pushQuestionByQid(context, qid)),
        const SizedBox(height: 10),
        if (!_srcOpen.contains(c['id']))
          OutlinedButton.icon(
            icon: const Icon(Icons.menu_book, size: 16),
            label: const Text('展开源题详解（机制原理）'),
            onPressed: () => _loadSrc(c))
        else
          _srcBlock(c),
        RateBar(kind: 'k', ref: c['id'], starred: c['starred'] == 1,
            onRated: () => _nav(1)),
      ],
      const SizedBox(height: 60),
    ]);
  }

  /// 卡背下方的源题详解区：题干 + 答案 + 完整解析
  Widget _srcBlock(Map c) {
    final id = c['id'] as int;
    final qs = _src[id];
    if (qs == null) {
      return const Padding(padding: EdgeInsets.all(16),
          child: Center(child: CircularProgressIndicator()));
    }
    if (_srcErr.contains(id)) {
      return Padding(padding: const EdgeInsets.only(top: 8),
        child: LoadError(msg: '源题加载失败', onRetry: () => _loadSrc(c)));
    }
    if (qs.isEmpty) {
      return const Padding(padding: EdgeInsets.only(top: 8),
          child: Text('该卡无关联源题', style: TextStyle(color: Colors.grey)));
    }
    final sub = Theme.of(context).colorScheme.outline;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Divider(height: 20),
      Text('📖 源题详解（${qs.length}）',
          style: const TextStyle(fontWeight: FontWeight.w700)),
      for (final q in qs)
        Container(
          margin: const EdgeInsets.only(top: 8),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey.shade300),
            borderRadius: BorderRadius.circular(10)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Q${q['qid']} · ${q['system'] ?? ''}',
                  style: TextStyle(fontSize: 11, color: sub)),
              const SizedBox(height: 4),
              HtmlView(q['stem'] ?? ''),
              if ((q['answer'] ?? '').toString().isNotEmpty)
                Text('答案：${q['answer']}',
                    style: const TextStyle(fontSize: 13,
                        color: Color(0xFF16A34A),
                        fontWeight: FontWeight.w600)),
              HtmlView(q['analysis'] ?? '',
                  onQref: (qid) => pushQuestionByQid(context, qid)),
            ]),
        ),
    ]);
  }
}
