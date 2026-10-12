import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';

class CardsPage extends StatefulWidget {
  const CardsPage({super.key});

  @override
  State<CardsPage> createState() => _CardsPageState();
}

class _CardsPageState extends State<CardsPage> {
  int _planDay = 0;

  @override
  void initState() {
    super.initState();
    _loadPlan();
  }

  Future<void> _loadPlan() async {
    int n = 0;
    try {
      final PlanToday p = await Endpoints.plan();
      n = p.configured && p.todayItems.isNotEmpty ? 1 : 0;
    } catch (_) {
      n = 0;
    }
    if (!mounted) return;
    setState(() => _planDay = n > 0 ? n : 0);
  }

  Widget _quick(IconData icon, String title, String desc, VoidCallback onTap) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return AppCard(
      onTap: onTap,
      child: Row(
        children: <Widget>[
          Icon(icon, color: cs.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(desc,
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
        ],
      ),
    );
  }

  Widget _partTile(CardPartIndex p) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      onTap: () => openCardRun(
          context, CardRunArgs(subject: p.subject, part: p.part)),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(p.part,
                style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
          Text('${p.count} 张',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
          const SizedBox(width: 4),
          Icon(Icons.chevron_right, size: 20, color: cs.onSurfaceVariant),
        ],
      ),
    );
  }

  Widget _body(List<CardPartIndex> index, Future<void> Function() refresh) {
    final Map<String, List<CardPartIndex>> groups =
        <String, List<CardPartIndex>>{};
    for (final CardPartIndex c in index) {
      groups.putIfAbsent(c.subject, () => <CardPartIndex>[]).add(c);
    }
    final List<Widget> children = <Widget>[
      _quick(Icons.alarm, '到期复习', '按遗忘曲线到期的卡片',
          () => openCardRun(context, const CardRunArgs(due: true))),
      const SizedBox(height: 12),
      _quick(Icons.star_outline, '收藏卡片', '你标星的重点考点',
          () => openCardRun(context, const CardRunArgs(starred: true))),
      if (_planDay > 0) ...<Widget>[
        const SizedBox(height: 12),
        _quick(Icons.event_note_outlined, '今日计划', '今日计划的背卡任务',
            () => openCardRun(context, CardRunArgs(planDay: _planDay))),
      ],
      const SizedBox(height: 20),
    ];
    if (groups.isEmpty) {
      children.add(const Padding(
        padding: EdgeInsets.only(top: 40),
        child: EmptyState('暂无卡片', icon: Icons.style_outlined),
      ));
    }
    groups.forEach((String subject, List<CardPartIndex> parts) {
      final int total = parts.fold<int>(0, (int n, CardPartIndex p) => n + p.count);
      children.add(Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          children: <Widget>[
            Flexible(
              child: Text(subject,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700)),
            ),
            const SizedBox(width: 8),
            AppBadge('$total 张'),
          ],
        ),
      ));
      for (final CardPartIndex p in parts) {
        children.add(_partTile(p));
        children.add(const SizedBox(height: 12));
      }
      children.add(const SizedBox(height: 8));
    });
    return AppRefreshIndicator(
      onRefresh: () async {
        await refresh();
        await _loadPlan();
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: children,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('背卡')),
      body: AsyncView<List<CardPartIndex>>(
        loader: Endpoints.cardIndex,
        builder: (BuildContext c, List<CardPartIndex> d,
                Future<void> Function() refresh) =>
            _body(d, refresh),
      ),
    );
  }
}
