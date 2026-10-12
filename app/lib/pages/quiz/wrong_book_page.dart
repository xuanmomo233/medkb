import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'quiz_fmt.dart';

class WrongBookPage extends StatelessWidget {
  const WrongBookPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('错题本')),
      body: AsyncView<List<WrongBookGroup>>(
        loader: Endpoints.wrongbook,
        builder: (BuildContext ctx, List<WrongBookGroup> groups,
            Future<void> Function() refresh) {
          int total = 0;
          for (final WrongBookGroup g in groups) {
            total += g.count;
          }
          if (groups.isEmpty) {
            return const EmptyState('暂无错题，继续保持', icon: Icons.celebration_outlined);
          }
          final ColorScheme cs = Theme.of(ctx).colorScheme;
          return AppRefreshIndicator(
            onRefresh: refresh,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text('共 $total 道错题',
                          style: TextStyle(color: cs.onSurfaceVariant)),
                    ),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(
                          minimumSize: const Size(48, 48)),
                      onPressed: () =>
                          openQuizRun(ctx, const QuizRunArgs(wrong: true)),
                      icon: const Icon(Icons.play_arrow, size: 20),
                      label: const Text('刷全部错题'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                for (final WrongBookGroup g in groups)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: AppCard(
                      onTap: () => openQuizRun(
                        ctx,
                        QuizRunArgs(
                          wrong: true,
                          filter: QuizFilter(chapter: g.chapter),
                        ),
                      ),
                      child: Row(
                        children: <Widget>[
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(g.chapter,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w700)),
                                const SizedBox(height: 4),
                                Text(
                                    '累计错 ${g.wrongTotal} 次 · 最近 ${fmtTime(g.lastWrongAt)}',
                                    style: TextStyle(
                                        fontSize: 12,
                                        color: cs.onSurfaceVariant)),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          AppBadge('${g.count} 题', tone: BadgeTone.bad),
                          Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
