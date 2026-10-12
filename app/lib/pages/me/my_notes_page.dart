import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show Note, TargetType;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import '../notes/note_time.dart';

class MyNotesPage extends StatefulWidget {
  const MyNotesPage({super.key});

  @override
  State<MyNotesPage> createState() => _MyNotesPageState();
}

class _MyNotesPageState extends State<MyNotesPage> {
  List<Note>? _notes;
  Object? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final List<Note> l = await Endpoints.notesMine();
      final List<Note> sorted = List<Note>.of(l)
        ..sort((Note a, Note b) => b.createdAt.compareTo(a.createdAt));
      if (!mounted) return;
      setState(() {
        _notes = sorted;
        _err = null;
      });
    } catch (e) {
      if (!mounted) return;
      if (_notes == null) {
        setState(() => _err = e);
      } else {
        toast(context, errText(e));
      }
    }
  }

  Future<bool> _remote(Note n) async {
    final bool ok = await confirmDialog(context, '删除笔记', '确定删除这条笔记吗？',
        okText: '删除');
    if (!ok) return false;
    try {
      await Endpoints.noteDelete(n.id);
      if (!mounted) return false;
      toast(context, '已删除');
      return true;
    } catch (e) {
      if (mounted) toast(context, errText(e));
      return false;
    }
  }

  void _removeLocal(Note n) {
    setState(() => _notes?.removeWhere((Note x) => x.id == n.id));
  }

  Future<void> _deleteBtn(Note n) async {
    final bool ok = await _remote(n);
    if (ok && mounted) _removeLocal(n);
  }

  void _open(Note n) {
    if (n.targetType == TargetType.card) {
      openCardRun(context, CardRunArgs(ids: <int>[n.targetId]));
    } else {
      openQuizRun(context, QuizRunArgs(ids: <int>[n.targetId]));
    }
  }

  @override
  Widget build(BuildContext context) {
    final List<Note>? notes = _notes;
    Widget body;
    if (_err != null && notes == null) {
      body = LoadError(
        msg: errText(_err!),
        onRetry: () {
          setState(() => _err = null);
          _load();
        },
      );
    } else if (notes == null) {
      body = const LoadingView();
    } else if (notes.isEmpty) {
      body = const EmptyState('还没有笔记，做题或背卡时可随手记录',
          icon: Icons.edit_note_outlined);
    } else {
      body = AppRefreshIndicator(
        onRefresh: _load,
        child: ListView.separated(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          itemCount: notes.length,
          separatorBuilder: (BuildContext _, int __) =>
              const SizedBox(height: 12),
          itemBuilder: (BuildContext ctx, int i) => _item(ctx, notes[i]),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('我的笔记')),
      body: body,
    );
  }

  Widget _item(BuildContext context, Note n) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool isCard = n.targetType == TargetType.card;
    final String preview = n.stemPreview ?? '';
    return Dismissible(
      key: ValueKey<int>(n.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (DismissDirection _) => _remote(n),
      onDismissed: (DismissDirection _) => _removeLocal(n),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(
          color: cs.errorContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(Icons.delete_outline, color: cs.onErrorContainer),
      ),
      child: AppCard(
        onTap: () => _open(n),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                AppBadge(isCard ? '卡片' : '题目',
                    tone: isCard ? BadgeTone.info : BadgeTone.primary),
                if (n.isPublic) ...<Widget>[
                  const SizedBox(width: 6),
                  const AppBadge('公开', tone: BadgeTone.good),
                ],
                const Spacer(),
                Text(fmtNoteTime(n.createdAt),
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                IconButton(
                  tooltip: '删除',
                  visualDensity: VisualDensity.compact,
                  icon: Icon(Icons.delete_outline,
                      size: 20, color: cs.onSurfaceVariant),
                  onPressed: () => _deleteBtn(n),
                ),
              ],
            ),
            if (preview.isNotEmpty) ...<Widget>[
              const SizedBox(height: 4),
              Text(preview,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant)),
            ],
            const SizedBox(height: 6),
            Text(n.body, style: const TextStyle(fontSize: 15, height: 1.5)),
          ],
        ),
      ),
    );
  }
}
