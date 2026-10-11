import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';

enum _Tab { mindmaps, notes, questions }

class _Item {
  final String key;
  final String label;
  final String extra;
  final VoidCallback onTap;
  const _Item(this.key, this.label, this.extra, this.onTap);
}

class _Group {
  final String name;
  final List<_Item> items;
  const _Group(this.name, this.items);
}

class BrowsePage extends StatefulWidget {
  const BrowsePage({super.key});

  @override
  State<BrowsePage> createState() => _BrowsePageState();
}

class _BrowsePageState extends State<BrowsePage> {
  _Tab _tab = _Tab.mindmaps;
  String _kw = '';

  List<_Group> _group(ContentTree tree) {
    final Map<String, List<_Item>> map = <String, List<_Item>>{};
    void push(String g, _Item it) {
      map.putIfAbsent(g, () => <_Item>[]).add(it);
    }

    if (_tab == _Tab.questions) {
      for (final QuestionChapterBrief c in tree.questionChapters) {
        push(
          c.subjectDir,
          _Item(
            '${c.subjectDir}/${c.system}/${c.chapter}',
            c.chapter,
            c.system,
            () => openQuizRun(
              context,
              QuizRunArgs(
                filter: QuizFilter(
                  chapter: c.chapter,
                  subjectDir: c.subjectDir,
                  system: c.system,
                ),
              ),
            ),
          ),
        );
      }
    } else {
      final List<ChapterBrief> src =
          _tab == _Tab.mindmaps ? tree.mindmaps : tree.notes;
      for (final ChapterBrief c in src) {
        push(c.subject,
            _Item('${c.id}', c.title, '', () => openChapter(context, c.id)));
      }
    }
    final List<_Group> out = <_Group>[];
    map.forEach((String k, List<_Item> v) => out.add(_Group(k, v)));
    final String kw = _kw.trim().toLowerCase();
    if (kw.isEmpty) return out;
    final List<_Group> res = <_Group>[];
    for (final _Group g in out) {
      if (g.name.toLowerCase().contains(kw)) {
        res.add(g);
        continue;
      }
      final List<_Item> items = g.items
          .where((_Item i) => '${i.label}${i.extra}'.toLowerCase().contains(kw))
          .toList();
      if (items.isNotEmpty) res.add(_Group(g.name, items));
    }
    return res;
  }

  Widget _groupTile(_Group g, bool filtering) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            key: ValueKey<String>('${_tab.name}:${g.name}:$filtering'),
            initiallyExpanded: filtering,
            title: Row(
              children: <Widget>[
                Flexible(
                  child: Text(g.name,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: 8),
                AppBadge('${g.items.length} 章'),
              ],
            ),
            children: g.items
                .map((_Item i) => ListTile(
                      title: Text(i.label),
                      subtitle: i.extra.isEmpty ? null : Text(i.extra),
                      trailing:
                          Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
                      onTap: i.onTap,
                    ))
                .toList(),
          ),
        ),
      ),
    );
  }

  Widget _content(ContentTree tree, Future<void> Function() refresh) {
    final List<_Group> groups = _group(tree);
    final bool filtering = _kw.trim().isNotEmpty;
    return RefreshIndicator(
      onRefresh: refresh,
      child: groups.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: <Widget>[
                const SizedBox(height: 80),
                EmptyState(filtering ? '没有匹配的章节' : '暂无内容'),
              ],
            )
          : ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              children: groups.map((_Group g) => _groupTile(g, filtering)).toList(),
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('目录'),
        actions: <Widget>[
          IconButton(
            tooltip: '搜索',
            icon: const Icon(Icons.search),
            onPressed: () => openSearch(context, ''),
          ),
        ],
      ),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Segmented<_Tab>(
              options: const <_Tab, String>{
                _Tab.mindmaps: '思维导图',
                _Tab.notes: '考点精要',
                _Tab.questions: '题库章节',
              },
              value: _tab,
              onChanged: (_Tab t) => setState(() => _tab = t),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              decoration: InputDecoration(
                hintText: '在本页过滤学科或章节',
                prefixIcon: const Icon(Icons.filter_list),
                isDense: true,
                suffixIcon: _kw.isEmpty
                    ? null
                    : IconButton(
                        tooltip: '清除',
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          _ctrl.clear();
                          setState(() => _kw = '');
                        },
                      ),
              ),
              controller: _ctrl,
              onChanged: (String v) => setState(() => _kw = v),
            ),
          ),
          Expanded(
            child: AsyncView<ContentTree>(
              loader: Endpoints.tree,
              builder: (BuildContext c, ContentTree t,
                      Future<void> Function() refresh) =>
                  _content(t, refresh),
            ),
          ),
        ],
      ),
    );
  }

  final TextEditingController _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }
}
