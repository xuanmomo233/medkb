import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';
import 'quiz_fmt.dart';

class ExamsPage extends StatelessWidget {
  const ExamsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('成绩记录')),
      body: AsyncView<List<ExamRecord>>(
        loader: Endpoints.exams,
        builder: (BuildContext ctx, List<ExamRecord> list,
            Future<void> Function() refresh) {
          if (list.isEmpty) {
            return EmptyState('还没有测试记录',
                icon: Icons.edit_note,
                action: OutlinedButton(
                    onPressed: () => Navigator.of(ctx).maybePop(),
                    child: const Text('去测试')));
          }
          final ColorScheme cs = Theme.of(ctx).colorScheme;
          return AppRefreshIndicator(
            onRefresh: refresh,
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: list.length,
              separatorBuilder: (BuildContext c, int i) =>
                  const SizedBox(height: 10),
              itemBuilder: (BuildContext c, int i) {
                final ExamRecord e = list[i];
                final Color col = rateColor(c, e.rate);
                return AppCard(
                  child: Row(
                    children: <Widget>[
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(e.title,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700)),
                            const SizedBox(height: 4),
                            Text(
                                '${fmtTime(e.createdAt)} · 答对 ${e.correct} / ${e.total}，答错 ${e.total - e.correct}',
                                style: TextStyle(
                                    fontSize: 12, color: cs.onSurfaceVariant)),
                            const SizedBox(height: 8),
                            ProgressBar(value: e.rate / 100, color: col),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text('${e.rate.round()}%',
                          style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                              color: col)),
                    ],
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
