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

class _SubGroup {
  final String name;
  final List<_Item> items;
  const _SubGroup(this.name, this.items);
}

class _Group {
  final String name;
  final List<_Item> items;
  final List<_SubGroup> subs;
  const _Group(this.name, this.items, [this.subs = const <_SubGroup>[]]);
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
      final List<_Group> out = <_Group>[];
      for (final QuestionSubjectBrief subj in tree.questionTree) {
        final List<_SubGroup> subs = <_SubGroup>[
          for (final QuestionSystemBrief sys in subj.systems)
            _SubGroup(
              sys.name,
              <_Item>[
                for (final QuestionChapterBrief c in sys.chapters)
                  _Item(
                    '${subj.subjectDir}/${sys.name}/${c.name}',
                    c.name.startsWith('${sys.name} · ')
                        ? c.name.substring(sys.name.length + 3)
                        : c.name,
                    '${c.count} 题',
                    () => openQuizRun(
                      context,
                      QuizRunArgs(
                        filter: QuizFilter(
                          chapter: c.name,
                          subjectDir: subj.subjectDir,
                          system: sys.name,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
        ];
        out.add(_Group(subj.subjectDir, <_Item>[], subs));
      }
      return _filter(out);
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
    return _filter(out);
  }

  List<_Group> _filter(List<_Group> out) {
    final String kw = _kw.trim().toLowerCase();
    if (kw.isEmpty) return out;
    bool hit(_Item i) => '${i.label}${i.extra}'.toLowerCase().contains(kw);
    final List<_Group> res = <_Group>[];
    for (final _Group g in out) {
      if (g.name.toLowerCase().contains(kw)) {
        res.add(g);
        continue;
      }
      if (g.subs.isNotEmpty) {
        final List<_SubGroup> subs = g.subs
            .map((_SubGroup s) => _SubGroup(s.name, s.items.where(hit).toList()))
            .where((_SubGroup s) =>
                s.name.toLowerCase().contains(kw) || s.items.isNotEmpty)
            .toList();
        if (subs.isNotEmpty) res.add(_Group(g.name, g.items, subs));
      } else {
        final List<_Item> items = g.items.where(hit).toList();
        if (items.isNotEmpty) res.add(_Group(g.name, items));
      }
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
                AppBadge(g.subs.isNotEmpty
                    ? '${g.subs.length} 篇'
                    : '${g.items.length} 章'),
              ],
            ),
            children: g.subs.isNotEmpty
                ? g.subs
                    .expand((_SubGroup sub) => <Widget>[
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
                            child: Text(sub.name,
                                style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: cs.primary)),
                          ),
                          ...sub.items.map((_Item i) => ListTile(
                                dense: true,
                                title: Text(i.label,
                                    style: const TextStyle(fontSize: 14)),
                                subtitle: i.extra.isEmpty
                                    ? null
                                    : Text(i.extra,
                                        style: const TextStyle(fontSize: 12)),
                                trailing: Icon(Icons.chevron_right,
                                    color: cs.onSurfaceVariant, size: 20),
                                onTap: i.onTap,
                              )),
                          const SizedBox(height: 6),
                        ])
                    .toList()
                : g.items
                    .map((_Item i) => ListTile(
                          title: Text(i.label),
                          subtitle:
                              i.extra.isEmpty ? null : Text(i.extra),
                          trailing: Icon(Icons.chevron_right,
                              color: cs.onSurfaceVariant),
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
