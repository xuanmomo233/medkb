import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';

class ExamReportPage extends StatefulWidget {
  final ExamReport report;
  final String title;
  const ExamReportPage(this.report, this.title, {super.key});

  @override
  State<ExamReportPage> createState() => _ExamReportPageState();
}

class _ExamReportPageState extends State<ExamReportPage> {
  String _redoMode = QuizMode.practice;

  String _num(double v) =>
      v == v.roundToDouble() ? v.toInt().toString() : v.toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final ExamReport r = widget.report;
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors c = AppColors.of(context);
    final int wrong = r.wrongIds.length;
    final int unjudged = r.results.where((ExamResultItem x) => !x.judged).length;
    return Scaffold(
      appBar: AppBar(title: Text('成绩单 · ${widget.title}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          AppCard(
            child: Column(
              children: <Widget>[
                Row(
                  children: <Widget>[
                    _Score(value: _num(r.score100), label: '百分制得分'),
                    _Score(value: _num(r.score300), label: '折算 300 分制'),
                    _Score(
                        value: '${r.correct}/${r.total}', label: '答对 / 总题数'),
                  ],
                ),
                if (unjudged > 0) ...<Widget>[
                  const SizedBox(height: 10),
                  Text('其中 $unjudged 题未作答，按错误计分。',
                      style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                ],
              ],
            ),
          ),
          const SizedBox(height: 12),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                const Text('分章节正确率',
                    style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 10),
                if (r.byChapter.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Center(
                        child: Text('没有可统计的作答',
                            style: TextStyle(color: cs.onSurfaceVariant))),
                  ),
                for (final ChapterRate ch in r.byChapter)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _chapterRow(ch, c),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    const Expanded(
                        child: Text('错题回顾',
                            style: TextStyle(fontWeight: FontWeight.w700))),
                    Text('共 $wrong 题',
                        style: TextStyle(color: cs.onSurfaceVariant)),
                  ],
                ),
                const SizedBox(height: 10),
                if (wrong == 0)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Center(
                        child: Text('全部答对，太棒了',
                            style: TextStyle(color: c.good))),
                  )
                else ...<Widget>[
                  Segmented<String>(
                    options: const <String, String>{
                      QuizMode.practice: '练习模式',
                      QuizMode.test: '测试模式',
                    },
                    value: _redoMode,
                    onChanged: (String v) => setState(() => _redoMode = v),
                  ),
                  const SizedBox(height: 10),
                  FilledButton(
                    style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 48)),
                    onPressed: () => openQuizRun(
                      context,
                      QuizRunArgs(
                        ids: r.wrongIds,
                        mode: _redoMode,
                        title: '错题重做',
                      ),
                    ),
                    child: const Text('重做错题'),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          OutlinedButton(
            style: OutlinedButton.styleFrom(minimumSize: const Size(0, 48)),
            onPressed: () => Navigator.of(context).maybePop(),
            child: const Text('返回'),
          ),
        ],
      ),
    );
  }

  Widget _chapterRow(ChapterRate ch, AppColors c) {
    final bool bad = ch.rate < 60;
    final Color col = bad ? c.bad : c.good;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(child: Text(ch.chapter)),
            Text(
              '${ch.correct}/${ch.total} · ${ch.rate.round()}%',
              style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600, color: col),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ProgressBar(value: ch.rate / 100, color: col),
      ],
    );
  }
}

class _Score extends StatelessWidget {
  final String value;
  final String label;
  const _Score({required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Expanded(
      child: Column(
        children: <Widget>[
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(value,
                style: TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                    color: cs.primary)),
          ),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
              textAlign: TextAlign.center),
        ],
      ),
    );
  }
}
