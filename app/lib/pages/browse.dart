import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets.dart';
import 'quiz.dart';

/// 目录浏览：导图 / 知识点 / 题库章节
class BrowsePage extends StatefulWidget {
  const BrowsePage({super.key});
  @override
  State<BrowsePage> createState() => _BrowseState();
}

class _BrowseState extends State<BrowsePage> {
  Map<String, List> tree = {};
  String filter = '';
  bool _loading = true;
  String? _err;
  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final t = await Api.get('/api/tree');
      tree = Map<String, List>.from(t);
      _err = null;
    } catch (_) {
      tree = {};
      _err = '目录加载失败，请检查网络';
    }
    _loading = false;
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('目录'), bottom: PreferredSize(
        preferredSize: const Size.fromHeight(52),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          child: TextField(
            decoration: InputDecoration(
              hintText: '过滤章节…', isDense: true,
              prefixIcon: const Icon(Icons.filter_list, size: 20),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onChanged: (v) => setState(() => filter = v.trim()),
          ),
        ),
      )),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _err != null && tree.isEmpty
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => _loading = true); _load(); })
          : tree.isEmpty
              ? const Center(child: Text('目录为空',
                  style: TextStyle(color: Colors.grey)))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(children: [
                for (final key in ['导图', '知识点', '题库']) _group(key),
              ]),
            ),
    );
  }

  Widget _group(String key) {
    final items = (tree[key] ?? []);
    final f = filter;
    if (key == '题库') {
      // 题库按 subjdir 分组的章节列表
      final byDir = <String, List>{};
      for (final c in items) {
        if (f.isNotEmpty && !(c['chapter'] as String).contains(f)) continue;
        byDir.putIfAbsent(c['subjdir'], () => []).add(c);
      }
      return _section(key, byDir.entries.map((e) =>
        ExpansionTile(title: Text(e.key,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
          subtitle: Text('${e.value.length} 章',
              style: const TextStyle(fontSize: 12)),
          children: e.value.map<Widget>((c) => ListTile(
            dense: true,
            title: Text(c['chapter'], style: const TextStyle(fontSize: 13.5)),
            onTap: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => QuizListPage(chapter: c['chapter'],
                    subjdir: c['subjdir']))),
          )).toList())).toList());
    }
    // 导图/知识点按 subj 分组
    final bySubj = <String, List>{};
    for (final c in items) {
      if (f.isNotEmpty &&
          !(c['title'] as String).contains(f) &&
          !(c['subj'] as String).contains(f)) continue;
      bySubj.putIfAbsent(c['subj'], () => []).add(c);
    }
    return _section(key, bySubj.entries.map((e) =>
      ExpansionTile(title: Text(e.key,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text('${e.value.length} 章', style: const TextStyle(fontSize: 12)),
        children: e.value.map<Widget>((c) => ListTile(
          dense: true,
          title: Text(c['title'], style: const TextStyle(fontSize: 13.5)),
          onTap: () => Navigator.push(context, MaterialPageRoute(
              builder: (_) => ChapterPage(id: c['id'], title: c['title']))),
        )).toList())).toList());
  }

  Widget _section(String title, List<Widget> children) {
    if (children.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 14, 14, 4),
        child: Text(title, style: TextStyle(fontSize: 13,
            fontWeight: FontWeight.w700,
            color: Theme.of(context).colorScheme.primary))),
      ...children,
    ]);
  }
}

/// 章节正文页
class ChapterPage extends StatelessWidget {
  final int id;
  final String title;
  const ChapterPage({super.key, required this.id, required this.title});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title, style: const TextStyle(fontSize: 16)),
        actions: [
          IconButton(icon: const Icon(Icons.format_size, size: 20),
              onPressed: () => showFontSheet(context)),
        ]),
      body: FutureBuilder(
        future: Api.get('/api/chapter?id=$id'),
        builder: (c, s) {
          if (s.hasError) {
            return const LoadError(msg: '章节加载失败');
          }
          if (!s.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final pages = (s.data['pages'] as List? ?? []);
          final meta = (s.data['meta'] as Map? ?? {});
          final pri = Theme.of(context).colorScheme.primary;
          Widget chip(IconData ic, String txt, Color bg, Color fg) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(ic, size: 13, color: fg), const SizedBox(width: 4),
              Text(txt, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: fg)),
            ]));
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (meta.isNotEmpty || pages.isNotEmpty)
                Wrap(spacing: 6, runSpacing: 6, children: [
                  if (meta['tags'] != null)
                    chip(Icons.bookmark, '${meta['tags']}', pri.withOpacity(0.12), pri),
                  if (meta['考试频率'] != null)
                    chip(Icons.whatshot, '${meta['考试频率']}',
                        const Color(0x20F59E0B), const Color(0xFFD97706)),
                  if (pages.isNotEmpty)
                    chip(Icons.picture_as_pdf, 'PDF ${pages.join('、')}页',
                        pri.withOpacity(0.08), pri),
                ]),
              if (meta.isNotEmpty || pages.isNotEmpty) const SizedBox(height: 12),
              if (pages.isNotEmpty) ...[
                Text('📄 原书页面对照（${pages.length}页，点击放大）',
                    style: TextStyle(fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: Theme.of(context).colorScheme.primary)),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final p in pages)
                    Semantics(
                      button: true,
                      label: '原书第 $p 页，点击放大',
                      onTap: () => showDialog(
                        context: context,
                        barrierColor: Colors.black.withOpacity(0.92),
                        builder: (_) => GestureDetector(
                          onTap: () => Navigator.of(context).pop(),
                          child: InteractiveViewer(maxScale: 6,
                            child: Image.network(
                                '${Api.base}/img/page_${p.toString().padLeft(3, '0')}.webp',
                                fit: BoxFit.contain)),
                        ),
                      ),
                      child: GestureDetector(
                      onTap: () => showDialog(
                        context: context,
                        barrierColor: Colors.black.withOpacity(0.92),
                        builder: (_) => GestureDetector(
                          onTap: () => Navigator.of(context).pop(),
                          child: InteractiveViewer(maxScale: 6,
                            child: Image.network(
                                '${Api.base}/img/page_${p.toString().padLeft(3, '0')}.webp',
                                fit: BoxFit.contain)),
                        ),
                      ),
                      child: Image.network(
                        '${Api.base}/img/page_${p.toString().padLeft(3, '0')}.webp',
                        width: 110,
                        loadingBuilder: (c, w, pr) => pr == null ? w
                            : const SizedBox(width: 110, height: 80,
                                child: Center(child:
                                    CircularProgressIndicator(strokeWidth: 2))),
                      ),
                    )),
                ]),
                const Divider(height: 24),
              ],
              HtmlView(s.data['html'] ?? '',
                  onQref: (qid) => pushQuestionByQid(context, qid)),
            ],
          );
        },
      ),
    );
  }
}
