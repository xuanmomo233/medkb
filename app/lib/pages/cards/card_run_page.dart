import 'dart:convert';
import 'package:flutter/material.dart' hide Card;
import 'package:shared_preferences/shared_preferences.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart';
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'card_runner.dart';

class CardLoaded {
  final List<Card> cards;
  final int idx;
  final Map<int, String> ratings;
  const CardLoaded(this.cards, this.idx, this.ratings);
}

String cardRunTitle(CardRunArgs a) {
  if (a.due) return '到期复习';
  if (a.starred) return '收藏卡片';
  if (a.planDay != null) return '今日计划 · 第 ${a.planDay} 天';
  if ((a.part ?? '').isNotEmpty) return '${a.subject ?? ''} · ${a.part}';
  if (a.ids != null) return '指定卡片';
  return '背卡';
}

class CardRunPage extends StatefulWidget {
  final CardRunArgs args;
  const CardRunPage(this.args, {super.key});

  @override
  State<CardRunPage> createState() => _CardRunPageState();
}

class _CardRunPageState extends State<CardRunPage> {
  int _round = 0;

  String get _key =>
      Api.prefKey('cpos', buildQuery(widget.args.toQuery().toQuery()));

  Future<CardLoaded> _load() async {
    final List<Card> cards = await Endpoints.cards(widget.args.toQuery());
    int idx = 0;
    final Map<int, String> ratings = <int, String>{};
    try {
      final SharedPreferences p = await SharedPreferences.getInstance();
      final String? raw = p.getString(_key);
      if (raw != null) {
        final Map<String, dynamic> j = asMap(jsonDecode(raw));
        final Object? i = j['idx'];
        if (i is num && i >= 0 && i <= cards.length) idx = i.toInt();
        asMap(j['ratings']).forEach((String k, dynamic v) {
          final int? id = int.tryParse(k);
          if (id != null && v is String) ratings[id] = v;
        });
      }
    } catch (_) {
      idx = 0;
      ratings.clear();
    }
    return CardLoaded(cards, idx, ratings);
  }

  Future<void> _restart() async {
    try {
      final SharedPreferences p = await SharedPreferences.getInstance();
      await p.remove(_key);
    } catch (_) {}
    if (!mounted) return;
    setState(() => _round++);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(cardRunTitle(widget.args))),
      body: AsyncView<CardLoaded>(
        loader: _load,
        reloadKey: _round,
        builder: (BuildContext c, CardLoaded d, Future<void> Function() r) {
          if (d.cards.isEmpty) {
            return EmptyState(
              '这里暂时没有可背的卡片',
              icon: Icons.celebration_outlined,
              action: FilledButton(
                onPressed: () => Navigator.of(c).pop(),
                child: const Text('返回'),
              ),
            );
          }
          return CardRunner(
            cards: d.cards,
            initialIdx: d.idx,
            initialRatings: d.ratings,
            storeKey: _key,
            onRestart: _restart,
          );
        },
      ),
    );
  }
}
