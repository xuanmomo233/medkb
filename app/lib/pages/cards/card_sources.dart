import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';

class CardSources extends StatefulWidget {
  final int cardId;
  const CardSources({super.key, required this.cardId});

  @override
  State<CardSources> createState() => _CardSourcesState();
}

class _CardSourcesState extends State<CardSources> {
  List<SourceQuestion>? _list;
  Object? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _err = null);
    try {
      final List<SourceQuestion> r = await Endpoints.cardSources(widget.cardId);
      if (!mounted) return;
      setState(() => _list = r);
    } catch (e) {
      if (!mounted) return;
      setState(() => _err = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final Object? err = _err;
    if (err != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          children: <Widget>[
            Text(errText(err), style: TextStyle(color: cs.onSurfaceVariant)),
            TextButton(onPressed: _load, child: const Text('重试')),
          ],
        ),
      );
    }
    final List<SourceQuestion>? list = _list;
    if (list == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (list.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text('该卡片暂无关联源题',
            style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant)),
      );
    }
    return Column(
      children: <Widget>[
        for (int i = 0; i < list.length; i++) _item(i, list[i], cs),
      ],
    );
  }

  Widget _item(int i, SourceQuestion q, ColorScheme cs) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: cs.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          title: Text('${i + 1}. ${plainHtml(q.stemHtml, 60)}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 14)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: AppBadge(q.qid, tone: BadgeTone.info),
            ),
          ),
          children: <Widget>[
            Text('${q.system} · ${q.qid}',
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
            const SizedBox(height: 8),
            HtmlView(q.stemHtml),
            const Divider(height: 20),
            HtmlView(q.analysisHtml.isEmpty ? '<p>暂无解析</p>' : q.analysisHtml),
          ],
        ),
      ),
    );
  }
}
