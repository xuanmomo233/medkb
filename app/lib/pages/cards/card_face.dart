import 'package:flutter/material.dart' hide Card;
import '../../models.dart';
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'card_run_page.dart';
import '../../api.dart';
import '../../endpoints.dart';
import 'source_questions_page.dart';

class CardFront extends StatelessWidget {
  final Card card;
  final VoidCallback onFlip;
  const CardFront({super.key, required this.card, required this.onFlip});

  @override
  Widget build(BuildContext context) {
    final ThemeData t = Theme.of(context);
    final ColorScheme cs = t.colorScheme;
    final String crumb =
        '${card.subject} · ${card.part}${card.section.isNotEmpty ? ' · ${card.section}' : ''}';
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onFlip,
      child: Semantics(
        button: true,
        label: '点击翻面',
        child: AppCard(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(crumb,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              const SizedBox(height: 28),
              if (card.termHtml.isEmpty)
                Text(card.term,
                    textAlign: TextAlign.center,
                    style: t.textTheme.headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w800, height: 1.4))
              else
                HtmlView(
                    '<div style="text-align:center;font-size:1.5em;font-weight:800;line-height:1.4">${card.termHtml}</div>'),
              if (card.hint.isNotEmpty) ...<Widget>[
                const SizedBox(height: 16),
                Text(card.hint,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: 14, height: 1.6, color: cs.onSurfaceVariant)),
              ],
              const SizedBox(height: 32),
              Text('点击翻面', style: TextStyle(fontSize: 12, color: cs.primary)),
            ],
          ),
        ),
      ),
    );
  }
}

class CardBack extends StatelessWidget {
  final Card card;
  const CardBack({super.key, required this.card});

  @override
  Widget build(BuildContext context) {
    final ThemeData t = Theme.of(context);
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (card.termHtml.isEmpty)
            Text(card.term,
                style: t.textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800))
          else
            HtmlView(
                '<div style="font-size:1.25em;font-weight:800">${card.termHtml}</div>'),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: <Widget>[
              if (card.state == ProgressState.mastered)
                const AppBadge('已掌握', tone: BadgeTone.good),
              if (card.state == ProgressState.again)
                const AppBadge('易忘', tone: BadgeTone.bad),
              if (card.starred) const AppBadge('已收藏', tone: BadgeTone.warn),
            ],
          ),
          const SizedBox(height: 10),
          HtmlView(card.bodyHtml),
          CitationList(card.citations),
          _SourceQuestionsButton(cardId: card.id),
          if (card.relatedCards.isNotEmpty) ...<Widget>[
            const Divider(height: 24),
            Text('关联知识', style: t.textTheme.titleMedium),
            for (final CardReference related in card.relatedCards)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${related.subject} · ${related.term}'),
                subtitle: Text(related.reason),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) =>
                      CardRunPage(CardRunArgs(ids: <int>[related.id])),
                )),
              ),
          ],
        ],
      ),
    );
  }
}

class _SourceQuestionsButton extends StatefulWidget {
  final int cardId;
  const _SourceQuestionsButton({required this.cardId});

  @override
  State<_SourceQuestionsButton> createState() => _SourceQuestionsButtonState();
}

class _SourceQuestionsButtonState extends State<_SourceQuestionsButton> {
  bool _busy = false;

  Future<void> _open() async {
    setState(() => _busy = true);
    try {
      final List<SourceQuestion> items = await Endpoints.cardSources(widget.cardId);
      if (!mounted) return;
      if (items.isEmpty) {
        toast(context, '本卡暂无关联源题');
      } else {
        await Navigator.of(context).push<void>(MaterialPageRoute<void>(
          builder: (_) => SourceQuestionsPage(list: items),
        ));
      }
    } catch (e) {
      if (mounted) toast(context, errText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => TextButton.icon(
    onPressed: _busy ? null : _open,
    icon: const Icon(Icons.menu_book, size: 18),
    label: Text(_busy ? '正在加载源题…' : '源题练习与解析'),
  );
}
