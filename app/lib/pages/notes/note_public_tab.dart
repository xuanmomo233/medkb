import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show NoteLikeResult, PublicNote;
import '../../widgets/widgets.dart';
import 'note_time.dart';

class PublicNotesTab extends StatefulWidget {
  final String targetType;
  final int targetId;
  const PublicNotesTab(
      {super.key, required this.targetType, required this.targetId});

  @override
  State<PublicNotesTab> createState() => _PublicNotesTabState();
}

class _PublicNotesTabState extends State<PublicNotesTab> {
  List<PublicNote>? _notes;
  Object? _err;
  final Set<int> _liking = <int>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final List<PublicNote> l =
          await Endpoints.publicNotes(widget.targetType, widget.targetId);
      final List<PublicNote> sorted = List<PublicNote>.of(l)
        ..sort((PublicNote a, PublicNote b) => b.likes.compareTo(a.likes));
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

  PublicNote _copy(PublicNote n, int likes, bool liked) => PublicNote(
        id: n.id,
        body: n.body,
        createdAt: n.createdAt,
        username: n.username,
        likes: likes,
        liked: liked,
        mine: n.mine,
      );

  void _replace(int id, PublicNote Function(PublicNote) f) {
    final List<PublicNote>? l = _notes;
    if (l == null) return;
    setState(() {
      _notes = l.map((PublicNote x) => x.id == id ? f(x) : x).toList();
    });
  }

  Future<void> _like(PublicNote n) async {
    if (_liking.contains(n.id)) return;
    _liking.add(n.id);
    final int oldLikes = n.likes;
    final bool oldLiked = n.liked;
    _replace(
        n.id,
        (PublicNote x) => _copy(
            x, oldLiked ? oldLikes - 1 : oldLikes + 1, !oldLiked));
    try {
      final NoteLikeResult r = await Endpoints.noteLike(n.id);
      if (!mounted) return;
      _replace(n.id, (PublicNote x) => _copy(x, r.likes, r.liked));
    } catch (e) {
      if (!mounted) return;
      _replace(n.id, (PublicNote x) => _copy(x, oldLikes, oldLiked));
      toast(context, errText(e));
    } finally {
      _liking.remove(n.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final List<PublicNote>? notes = _notes;
    if (_err != null && notes == null) {
      return LoadError(
        msg: errText(_err!),
        onRetry: () {
          setState(() => _err = null);
          _load();
        },
      );
    }
    if (notes == null) return const LoadingView();
    if (notes.isEmpty) {
      return const EmptyState('暂无公开讨论，来发表第一条吧',
          icon: Icons.forum_outlined);
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: notes.length,
      separatorBuilder: (BuildContext _, int __) => const SizedBox(height: 10),
      itemBuilder: (BuildContext ctx, int i) {
        final PublicNote n = notes[i];
        return AppCard(
          padding: const EdgeInsets.fromLTRB(14, 10, 8, 10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        Flexible(
                          child: Text(n.username,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600, fontSize: 13)),
                        ),
                        if (n.mine) ...<Widget>[
                          const SizedBox(width: 6),
                          const AppBadge('我的', tone: BadgeTone.primary),
                        ],
                        const SizedBox(width: 8),
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
              InkWell(
                onTap: () => _like(n),
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  constraints:
                      const BoxConstraints(minWidth: 48, minHeight: 48),
                  alignment: Alignment.center,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Icon(
                        n.liked ? Icons.thumb_up : Icons.thumb_up_outlined,
                        size: 20,
                        color: n.liked ? cs.primary : cs.onSurfaceVariant,
                      ),
                      Text('${n.likes}',
                          style: TextStyle(
                              fontSize: 12,
                              color:
                                  n.liked ? cs.primary : cs.onSurfaceVariant)),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
