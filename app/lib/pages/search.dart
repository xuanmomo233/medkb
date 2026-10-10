import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets.dart';
import 'quiz.dart';
import 'cards.dart';
import 'browse.dart';

class SearchPage extends StatefulWidget {
  const SearchPage({super.key});
  @override
  State<SearchPage> createState() => _SearchState();
}

class _SearchState extends State<SearchPage> {
  final q = TextEditingController();
  List results = [];
  bool busy = false, _searched = false;
  String? _err;

  Future<void> _go() async {
    if (q.text.trim().isEmpty) return;
    setState(() { busy = true; _err = null; _searched = true; });
    try {
      results = await Api.get(
          '/api/search?q=${Uri.encodeComponent(q.text.trim())}');
    } catch (_) { results = []; _err = '搜索失败，请检查网络'; }
    if (mounted) setState(() { busy = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: TextField(
        controller: q,
        decoration: const InputDecoration(
            hintText: '搜体征 / 病名 / 口诀 / 机制…', border: InputBorder.none),
        onSubmitted: (_) => _go(),
      ), actions: [
        IconButton(icon: const Icon(Icons.search), onPressed: _go),
      ]),
      body: busy
          ? const Center(child: CircularProgressIndicator())
          : _err != null
              ? LoadError(msg: _err!, onRetry: _go)
          : results.isEmpty
              ? Center(child: Text(_searched
                  ? '没有找到相关内容，换个关键词试试'
                  : '输入关键词搜索 7.1万题 + 7600考点',
                  style: const TextStyle(color: Colors.grey)))
              : ListView.separated(
                  itemCount: results.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (c, i) => _tile(results[i]),
                ),
    );
  }

  Widget _tile(Map r) {
    const icons = {'q': '❓', 'k': '📌', 'c': '📄'};
    return ListTile(
      leading: Text(icons[r['kind']] ?? '📄', style: const TextStyle(fontSize: 22)),
      title: Text(r['title'] ?? '', maxLines: 1, overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      subtitle: Text(r['snip'] ?? '', maxLines: 2, overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 12.5)),
      trailing: r['starred'] == 1 ? const Icon(Icons.star, size: 16, color: Colors.amber) : null,
      onTap: () {
        Widget page;
        if (r['kind'] == 'q') {
          page = QuizListPage(ids: [r['ref_id']]);
        } else if (r['kind'] == 'k') {
          page = CardRunPage(ids: [r['ref_id']]);
        } else {
          page = ChapterPage(id: r['ref_id'], title: r['title'] ?? '');
        }
        Navigator.push(context, MaterialPageRoute(builder: (_) => page));
      },
    );
  }
}
