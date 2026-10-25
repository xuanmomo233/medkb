import 'package:flutter/material.dart';
import '../../api.dart' show errText;
import '../../endpoints.dart';
import '../../models.dart' show RelatedQuestion;
import '../../nav.dart';
import '../../widgets/widgets.dart';

class RelatedQuestions extends StatefulWidget {
  final int questionId;
  final Future<void> Function()? onPracticed;
  const RelatedQuestions({super.key, required this.questionId, this.onPracticed});

  @override
  State<RelatedQuestions> createState() => _RelatedQuestionsState();
}

class _RelatedQuestionsState extends State<RelatedQuestions> {
  late Future<List<RelatedQuestion>> _future;

  @override
  void initState() {
    super.initState();
    _future = Endpoints.relatedQuestions(widget.questionId);
  }

  @override
  void didUpdateWidget(covariant RelatedQuestions oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.questionId != widget.questionId) {
      _future = Endpoints.relatedQuestions(widget.questionId);
    }
  }

  Future<void> _practice(RelatedQuestion item) async {
    await openQuizRun(context, QuizRunArgs(ids: <int>[item.id], fresh: true));
    if (!mounted) return;
    setState(() => _future = Endpoints.relatedQuestions(widget.questionId));
    await widget.onPracticed?.call();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: <Widget>[
      const SizedBox(height: 12),
      Text('同类题巩固', style: Theme.of(context).textTheme.titleSmall),
      FutureBuilder<List<RelatedQuestion>>(
        future: _future,
        builder: (BuildContext context, AsyncSnapshot<List<RelatedQuestion>> snapshot) {
          if (snapshot.hasError) {
            return Row(children: <Widget>[
              Expanded(child: Text('同类题加载失败：${errText(snapshot.error!)}')),
              TextButton(onPressed: () => setState(() => _future = Endpoints.relatedQuestions(widget.questionId)),
                child: const Text('重试')),
            ]);
          }
          if (snapshot.connectionState != ConnectionState.done) return const Text('正在查找同类题…');
          final List<RelatedQuestion> items = snapshot.data!;
          if (items.isEmpty) return const Text('暂无未做的同类题推荐');
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: items.map((RelatedQuestion item) => Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: <Widget>[
                Wrap(spacing: 6, children: <Widget>[
                  AppBadge(item.label, tone: BadgeTone.info),
                  AppBadge(item.inPlan ? '计划内待做' : '未做'),
                ]),
                const SizedBox(height: 6),
                Text(item.stem),
                if (item.reason.isNotEmpty) Text(item.reason),
                Align(alignment: Alignment.centerLeft, child: TextButton(
                  onPressed: () => _practice(item), child: const Text('练这一题'),
                )),
              ]),
            )).toList(),
          );
        },
      ),
    ],
  );
}
