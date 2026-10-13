import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart' hide Card;
import 'package:shared_preferences/shared_preferences.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart';
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';
import 'card_face.dart';
import 'card_summary.dart';

class CardRunner extends StatefulWidget {
  final List<Card> cards;
  final int initialIdx;
  final Map<int, String> initialRatings;
  final String storeKey;
  final Future<void> Function() onRestart;
  const CardRunner({
    super.key,
    required this.cards,
    required this.initialIdx,
    required this.initialRatings,
    required this.storeKey,
    required this.onRestart,
  });

  @override
  State<CardRunner> createState() => _CardRunnerState();
}

class _CardRunnerState extends State<CardRunner> {
  late List<Card> _cards = List<Card>.of(widget.cards);
  late final Map<int, String> _ratings =
      Map<int, String>.of(widget.initialRatings);
  late int _idx = widget.initialIdx;
  late final PageController _pc = PageController(initialPage: widget.initialIdx);
  bool _flipped = false;

  int get _total => _cards.length;

  @override
  void dispose() {
    _pc.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    try {
      final SharedPreferences p = await SharedPreferences.getInstance();
      await p.setString(
        widget.storeKey,
        jsonEncode(<String, Object?>{
          'idx': _idx,
          'ratings': _ratings.map((int k, String v) => MapEntry<String, String>('$k', v)),
        }),
      );
    } catch (_) {}
  }

  void _go(int n) {
    final int t = n < 0 ? 0 : (n > _total ? _total : n);
    if (!_pc.hasClients) return;
    if (MediaQuery.of(context).disableAnimations) {
      _pc.jumpToPage(t);
    } else {
      _pc.animateToPage(t,
          duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    }
  }

  void _patch(int id, {
    String? section,
    String? term,
    String? termHtml,
    String? hint,
    String? bodyHtml,
    String? state,
    bool? starred,
  }) {
    setState(() {
      _cards = _cards.map((Card c) {
        if (c.id != id) return c;
        return Card(
          id: c.id,
          subject: c.subject,
          part: c.part,
          section: section ?? c.section,
          term: term ?? c.term,
          termHtml: termHtml ?? c.termHtml,
          hint: hint ?? c.hint,
          bodyHtml: bodyHtml ?? c.bodyHtml,
          state: state ?? c.state,
          starred: starred ?? c.starred,
        );
      }).toList();
    });
  }

  Future<void> _editCard(int id) async {
    final bool saved = await openAdminCardEdit(context, id);
    if (!mounted || !saved) return;
    try {
      final List<Card> updated = await Endpoints.cards(CardQuery(ids: <int>[id]), cache: false);
      if (!mounted || updated.isEmpty) return;
      final Card c = updated.first;
      _patch(id,
          section: c.section,
          term: c.term,
          termHtml: c.termHtml,
          hint: c.hint,
          bodyHtml: c.bodyHtml);
    } catch (e) {
      if (mounted) toast(context, errText(e));
    }
  }

  Future<bool> _send(int id, String action) async {
    try {
      await Endpoints.mark(TargetType.card, id, action);
      return true;
    } catch (e) {
      if (mounted) toast(context, errText(e));
      return false;
    }
  }

  void _rate(String action) {
    if (_idx >= _total) return;
    final Card card = _cards[_idx];
    _ratings[card.id] = action;
    if (action != MarkAction.rateHard) {
      _patch(card.id,
          state: action == MarkAction.rateGood
              ? ProgressState.mastered
              : ProgressState.again);
    }
    unawaited(_send(card.id, action));
    _go(_idx + 1);
    unawaited(_save());
  }

  Future<void> _toggleStar() async {
    if (_idx >= _total) return;
    final Card card = _cards[_idx];
    final bool next = !card.starred;
    _patch(card.id, starred: next);
    final bool ok = await _send(card.id, next ? MarkAction.star : MarkAction.unstar);
    if (!mounted) return;
    if (ok) {
      toast(context, next ? '已收藏' : '已取消收藏');
    } else {
      _patch(card.id, starred: !next);
    }
  }

  Future<void> _addPlan() async {
    if (_idx >= _total) return;
    final int id = _cards[_idx].id;
    final bool ok = await _send(id, MarkAction.plan);
    if (!mounted || !ok) return;
    _patch(id, state: ProgressState.plan);
    toast(context, '已加入复习');
  }

  void _openJump() {
    showAppSheet<void>(
      context,
      title: '跳转到第几张',
      builder: (BuildContext ctx) {
        final AppColors c = AppColors.of(ctx);
        return GridView.builder(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 56,
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
          ),
          itemCount: _total,
          itemBuilder: (BuildContext _, int i) {
            final bool rated = _ratings.containsKey(_cards[i].id);
            final bool cur = i == _idx;
            return InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () {
                Navigator.of(ctx).pop();
                _go(i);
              },
              child: Container(
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: rated ? c.goodSoft : null,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: cur
                        ? Theme.of(ctx).colorScheme.primary
                        : Theme.of(ctx).colorScheme.outlineVariant,
                    width: cur ? 2 : 1,
                  ),
                ),
                child: Text('${i + 1}',
                    style: TextStyle(
                        color: rated ? c.good : null,
                        fontWeight: cur ? FontWeight.w700 : FontWeight.w400)),
              ),
            );
          },
        );
      },
    );
  }

  Widget _stage(int i) {
    if (i >= _total) {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: CardSummary(
          total: _total,
          ratings: _ratings,
          onRestart: () => widget.onRestart(),
          onPrev: () => _go(_total - 1),
        ),
      );
    }
    final Card card = _cards[i];
    final bool flipped = i == _idx && _flipped;
    final Duration d = MediaQuery.of(context).disableAnimations
        ? Duration.zero
        : const Duration(milliseconds: 220);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: AnimatedSwitcher(
        duration: d,
        child: flipped
            ? CardBack(key: ValueKey<String>('b${card.id}'), card: card)
            : CardFront(
                key: ValueKey<String>('f${card.id}'),
                card: card,
                onFlip: () {
                  if (i == _idx) setState(() => _flipped = true);
                },
              ),
      ),
    );
  }

  Widget _topBar() {
    final bool onCard = _idx < _total;
    final Card? card = onCard ? _cards[_idx] : null;
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 8, 0),
      child: Row(
        children: <Widget>[
          TextButton.icon(
            onPressed: _openJump,
            icon: const Icon(Icons.grid_view, size: 18),
            label: Text('${_idx < _total ? _idx + 1 : _total} / $_total'),
          ),
          const Spacer(),
          if (card != null) ...<Widget>[
            IconButton(
              tooltip: card.starred ? '取消收藏' : '收藏',
              icon: Icon(card.starred ? Icons.star : Icons.star_border,
                  color: card.starred ? AppColors.of(context).warn : null),
              onPressed: _toggleStar,
            ),
            IconButton(
              tooltip: '加入复习',
              icon: Icon(
                  card.state == ProgressState.plan
                      ? Icons.bookmark_added
                      : Icons.bookmark_add_outlined,
                  color: card.state == ProgressState.plan ? cs.primary : null),
              onPressed: _addPlan,
            ),
            IconButton(
              tooltip: '笔记',
              icon: const Icon(Icons.edit_note),
              onPressed: () => openNotes(context,
                  targetType: TargetType.card, targetId: card.id),
            ),
            if (Api.admin)
              IconButton(
                tooltip: '编辑卡片',
                icon: const Icon(Icons.edit_outlined),
                onPressed: () => _editCard(card.id),
              ),
          ],
        ],
      ),
    );
  }

  Widget _rateButton(String label, String action, Color fg, Color bg) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: bg,
            foregroundColor: fg,
            minimumSize: const Size(0, 52),
          ),
          onPressed: () => _rate(action),
          child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
      ),
    );
  }

  Widget _bottomBar() {
    if (_idx >= _total) return const SizedBox.shrink();
    final AppColors c = AppColors.of(context);
    final ThemeData t = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: t.colorScheme.surface,
        border: Border(top: BorderSide(color: t.colorScheme.outlineVariant)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          child: _flipped
              ? Row(
                  children: <Widget>[
                    _rateButton('忘了', MarkAction.rateAgain, c.bad, c.badSoft),
                    _rateButton('模糊', MarkAction.rateHard, c.warn, c.warnSoft),
                    _rateButton('记住', MarkAction.rateGood, c.good, c.goodSoft),
                  ],
                )
              : SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 52)),
                    onPressed: () => setState(() => _flipped = true),
                    child: const Text('翻面'),
                  ),
                ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        _topBar(),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: ProgressBar(
              value: _total == 0 ? 0 : (_idx > _total ? _total : _idx) / _total),
        ),
        Expanded(
          child: PageView.builder(
            controller: _pc,
            itemCount: _total + 1,
            onPageChanged: (int i) {
              setState(() {
                _idx = i;
                _flipped = false;
              });
              unawaited(_save());
            },
            itemBuilder: (BuildContext c, int i) => _stage(i),
          ),
        ),
        _bottomBar(),
      ],
    );
  }
}
