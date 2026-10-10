import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets.dart';
import 'quiz.dart';
import 'cards.dart';

String _stripHtml(String s) =>
    s.replaceAll(RegExp(r'<[^>]+>'), '').replaceAll(RegExp(r'\s+'), ' ').trim();

/// 「笔记」底部弹窗：查看该题/该卡已有笔记 + 追加新笔记（kind=q 题 / k 背卡）
class NoteSheet extends StatefulWidget {
  final int ref;
  final String kind;
  const NoteSheet({super.key, required this.ref, this.kind = 'q'});
  @override
  State<NoteSheet> createState() => _NoteSheetState();
}

class _NoteSheetState extends State<NoteSheet> {
  List notes = [];
  bool loading = true;
  String? _err;
  final c = TextEditingController();

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      notes = await Api.get(
          '/api/note?kind=${widget.kind}&ref=${widget.ref}', cache: false);
      _err = null;
    } catch (_) { notes = []; _err = '笔记加载失败'; }
    loading = false;
    if (mounted) setState(() {});
  }

  Future<void> _save() async {
    final t = c.text.trim();
    if (t.isEmpty) return;
    try {
      await Api.post('/api/note',
          {'kind': widget.kind, 'ref': widget.ref, 'body': t});
    } catch (_) {
      if (mounted) toast(context, '保存失败，请检查网络');
      return;
    }
    c.clear();
    _load();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('笔记已保存'), duration: Duration(seconds: 1),
          behavior: SnackBarBehavior.floating));
    }
  }

  Future<void> _del(int id) async {
    try {
      await Api.del('/api/note', {'id': id});
    } catch (_) {
      if (mounted) toast(context, '删除失败，请检查网络');
      return;
    }
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: Container(
          constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.7),
          padding: const EdgeInsets.all(14),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Row(children: [
              const Text('📝 本题笔记', style: TextStyle(fontWeight: FontWeight.w700)),
              const Spacer(),
              Text('${notes.length} 条',
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ]),
            const SizedBox(height: 8),
            Flexible(
              child: loading
                  ? const Padding(padding: EdgeInsets.all(24),
                      child: Center(child: CircularProgressIndicator()))
                  : _err != null
                      ? Padding(padding: const EdgeInsets.all(20),
                          child: Column(mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(_err!, style: const TextStyle(
                                  color: Colors.grey)),
                              const SizedBox(height: 8),
                              OutlinedButton(onPressed: () {
                                setState(() => loading = true);
                                _load();
                              }, child: const Text('重试')),
                            ]))
                  : notes.isEmpty
                      ? const Padding(padding: EdgeInsets.all(20),
                          child: Text('还没有笔记，写下你的解题思路吧',
                              style: TextStyle(color: Colors.grey)))
                      : ListView.builder(
                          shrinkWrap: true,
                          itemCount: notes.length,
                          itemBuilder: (_, k) {
                            final n = notes[k];
                            final t = DateTime.fromMillisecondsSinceEpoch(
                                ((n['updated'] ?? 0) * 1000).round());
                            return Card(
                              child: ListTile(
                                dense: true,
                                title: Text(n['body'] ?? ''),
                                subtitle: Text(
                                    '${t.month}-${t.day} ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}',
                                    style: const TextStyle(fontSize: 11)),
                                trailing: IconButton(
                                  icon: const Icon(Icons.delete_outline, size: 18),
                                  onPressed: () => _del(n['id'])),
                              ),
                            );
                          }),
            ),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: TextField(
                controller: c,
                maxLines: 4, minLines: 1,
                decoration: const InputDecoration(
                  hintText: '记录思路 / 易错点 / 记忆口诀…',
                  border: OutlineInputBorder(), isDense: true),
              )),
              const SizedBox(width: 8),
              FilledButton(onPressed: _save, child: const Text('保存')),
            ]),
          ]),
        ),
      ),
    );
  }
}

/// 我的笔记：全部笔记列表，点击跳到对应题目
class NotesPage extends StatefulWidget {
  const NotesPage({super.key});
  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  List notes = [];
  bool loading = true;
  String? _err;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try { notes = await Api.get('/api/notes', cache: false); _err = null; }
    catch (_) { notes = []; _err = '笔记加载失败'; }
    loading = false;
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('我的笔记'), actions: [
        IconButton(icon: const Icon(Icons.refresh), onPressed: () {
          setState(() => loading = true); _load();
        }),
      ]),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : _err != null
              ? LoadError(msg: _err!, onRetry: () {
                  setState(() => loading = true); _load(); })
          : notes.isEmpty
              ? const Center(child: Text('还没有笔记\n刷题时点右上角 📝 记录思路',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey)))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: notes.length,
                    itemBuilder: (_, k) {
                      final n = notes[k];
                      final t = DateTime.fromMillisecondsSinceEpoch(
                          ((n['updated'] ?? 0) * 1000).round());
                      final stem = _stripHtml((n['stem'] ?? '').toString());
                      final ref = int.tryParse((n['ref'] ?? '').toString());
                      return Card(
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: ref == null ? null : () =>
                              Navigator.push(context, MaterialPageRoute(
                                  builder: (_) => n['kind'] == 'k'
                                      ? CardRunPage(ids: [ref])
                                      : QuizListPage(ids: [ref]))),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(n['body'] ?? '',
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w600)),
                                if (stem.isNotEmpty) ...[
                                  const SizedBox(height: 6),
                                  Text(stem,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                          fontSize: 12, color: Colors.grey)),
                                ],
                                const SizedBox(height: 4),
                                Row(children: [
                                  Text('${t.year}-${t.month.toString().padLeft(2, '0')}-${t.day.toString().padLeft(2, '0')} '
                                      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}',
                                      style: const TextStyle(
                                          fontSize: 11, color: Colors.grey)),
                                  const Spacer(),
                                  IconButton(
                                    tooltip: '删除笔记',
                                    visualDensity: VisualDensity.compact,
                                    onPressed: () async {
                                      try {
                                        await Api.del('/api/note',
                                            {'id': n['id']});
                                      } catch (_) {
                                        if (context.mounted) {
                                          toast(context, '删除失败，请检查网络');
                                        }
                                        return;
                                      }
                                      _load();
                                    },
                                    icon: const Icon(Icons.delete_outline,
                                        size: 18, color: Colors.grey),
                                  ),
                                ]),
                              ]),
                          ),
                        ),
                      );
                    }),
                ),
    );
  }
}
