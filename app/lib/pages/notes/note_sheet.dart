import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show Note;
import '../../widgets/widgets.dart';
import 'note_public_tab.dart';
import 'note_time.dart';

class NoteSheet extends StatefulWidget {
  final String targetType;
  final int targetId;
  const NoteSheet({super.key, required this.targetType, required this.targetId});

  @override
  State<NoteSheet> createState() => _NoteSheetState();
}

class _NoteSheetState extends State<NoteSheet> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final double h = MediaQuery.of(context).size.height * 0.72;
    return SizedBox(
      height: h,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Segmented<int>(
              options: const <int, String>{0: '我的笔记', 1: '公开讨论'},
              value: _tab,
              onChanged: (int v) => setState(() => _tab = v),
            ),
          ),
          Expanded(
            child: _tab == 0
                ? MyNotesTab(
                    targetType: widget.targetType, targetId: widget.targetId)
                : PublicNotesTab(
                    targetType: widget.targetType, targetId: widget.targetId),
          ),
        ],
      ),
    );
  }
}

class MyNotesTab extends StatefulWidget {
  final String targetType;
  final int targetId;
  const MyNotesTab({super.key, required this.targetType, required this.targetId});

  @override
  State<MyNotesTab> createState() => _MyNotesTabState();
}

class _MyNotesTabState extends State<MyNotesTab> {
  final TextEditingController _ctl = TextEditingController();
  List<Note>? _notes;
  Object? _err;
  bool _public = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final List<Note> l =
          await Endpoints.notesOf(widget.targetType, widget.targetId);
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

  Future<void> _publish() async {
    final String body = _ctl.text.trim();
    if (body.isEmpty || _busy) return;
    setState(() => _busy = true);
    try {
      await Endpoints.noteAdd(widget.targetType, widget.targetId, body, _public);
      if (!mounted) return;
      _ctl.clear();
      setState(() => _busy = false);
      toast(context, _public ? '已公开发布' : '已保存');
      _load();
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, errText(e));
    }
  }

  Future<void> _delete(Note n) async {
    final bool ok =
        await confirmDialog(context, '删除笔记', '确定删除这条笔记吗？', okText: '删除');
    if (!ok) return;
    try {
      await Endpoints.noteDelete(n.id);
      if (!mounted) return;
      setState(() => _notes?.removeWhere((Note x) => x.id == n.id));
    } catch (e) {
      if (mounted) toast(context, errText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final List<Note>? notes = _notes;
    Widget list;
    if (_err != null && notes == null) {
      list = LoadError(
        msg: errText(_err!),
        onRetry: () {
          setState(() => _err = null);
          _load();
        },
      );
    } else if (notes == null) {
      list = const LoadingView();
    } else if (notes.isEmpty) {
      list = const EmptyState('还没有笔记，写下你的理解吧', icon: Icons.edit_note_outlined);
    } else {
      list = ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: notes.length,
        separatorBuilder: (BuildContext _, int __) => const SizedBox(height: 10),
        itemBuilder: (BuildContext ctx, int i) {
          final Note n = notes[i];
          return AppCard(
            padding: const EdgeInsets.fromLTRB(14, 10, 4, 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Row(
                        children: <Widget>[
                          if (n.isPublic) ...<Widget>[
                            const AppBadge('公开', tone: BadgeTone.good),
                            const SizedBox(width: 6),
                          ],
                          Text(fmtNoteTime(n.createdAt),
                              style: TextStyle(
                                  fontSize: 12, color: cs.onSurfaceVariant)),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(n.body, style: const TextStyle(height: 1.5)),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: '删除',
                  icon: Icon(Icons.delete_outline, color: cs.onSurfaceVariant),
                  onPressed: () => _delete(n),
                ),
              ],
            ),
          );
        },
      );
    }
    return Column(
      children: <Widget>[
        Expanded(child: list),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              TextField(
                controller: _ctl,
                minLines: 1,
                maxLines: 4,
                maxLength: 2000,
                enabled: !_busy,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  hintText: '写点笔记…',
                  counterText: '',
                  isDense: true,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: <Widget>[
                  Switch(
                    value: _public,
                    onChanged: (bool v) => setState(() => _public = v),
                  ),
                  const SizedBox(width: 4),
                  const Expanded(child: Text('公开发布')),
                  FilledButton(
                    onPressed:
                        (_busy || _ctl.text.trim().isEmpty) ? null : _publish,
                    child: Text(_busy ? '提交中…' : '发布'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

Future<void> showNoteSheet(BuildContext context,
    {required String targetType, required int targetId}) async {
  await showAppSheet<void>(
    context,
    title: '笔记',
    builder: (BuildContext ctx) =>
        NoteSheet(targetType: targetType, targetId: targetId),
  );
}
