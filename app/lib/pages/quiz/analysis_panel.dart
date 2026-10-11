import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import '../../widgets/widgets.dart';

class AnalysisPanel extends StatelessWidget {
  final Question q;
  final String picked;
  final bool judged;
  final bool? correct;
  final QuestionFull? full;
  final bool failed;
  final QuestionStat? stat;
  final bool aiBusy;
  final VoidCallback onRetry;
  final VoidCallback onAi;
  const AnalysisPanel({
    super.key,
    required this.q,
    required this.picked,
    required this.judged,
    required this.correct,
    required this.full,
    required this.failed,
    required this.stat,
    required this.aiBusy,
    required this.onRetry,
    required this.onAi,
  });

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors c = AppColors.of(context);
    final QuestionFull? f = full;
    final QuestionStat? st = stat ?? f?.stat;
    int? rate;
    if (st != null && st.total > 0) {
      rate = ((st.correct * 100) / st.total).round();
    }
    final List<String> tags = f != null && f.tags.isNotEmpty ? f.tags : q.tags;
    final TextStyle title = TextStyle(
        fontWeight: FontWeight.w700, fontSize: 14, color: cs.primary);

    final List<Widget> body = <Widget>[
      Wrap(
        spacing: 10,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: <Widget>[
          Text.rich(TextSpan(children: <InlineSpan>[
            const TextSpan(text: '正确答案 '),
            TextSpan(
                text: q.answer,
                style: TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 18, color: c.good)),
          ])),
          if (judged && picked.isNotEmpty) Text('你的选择 $picked'),
          if (judged && correct == true)
            const AppBadge('✓ 回答正确', tone: BadgeTone.good),
          if (judged && correct == false)
            const AppBadge('✗ 回答错误', tone: BadgeTone.bad),
        ],
      ),
    ];

    if (rate != null && st != null) {
      body.add(const SizedBox(height: 12));
      body.add(Text('全站正确率 $rate%（${st.correct}/${st.total}）',
          style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)));
      body.add(const SizedBox(height: 4));
      body.add(ProgressBar(
          value: rate / 100, color: rate >= 60 ? c.good : c.bad));
    }

    body.add(const SizedBox(height: 12));
    if (f == null && !failed) {
      body.add(const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(
            child: SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2.4))),
      ));
    } else if (f == null) {
      body.add(Row(
        children: <Widget>[
          Text('解析加载失败', style: TextStyle(color: c.bad)),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ));
    } else if (f.analysisHtml.isNotEmpty) {
      body.add(Text('解析', style: title));
      body.add(const SizedBox(height: 6));
      body.add(HtmlView(f.analysisHtml));
    } else {
      body.add(Text('本题暂无解析', style: title));
      for (final RelatedCard rc in f.relatedCards) {
        body.add(const SizedBox(height: 10));
        body.add(Text(rc.term,
            style: const TextStyle(fontWeight: FontWeight.w700)));
        if (rc.hint.isNotEmpty) {
          body.add(Text(rc.hint,
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)));
        }
        body.add(HtmlView(rc.bodyHtml));
      }
      body.add(const SizedBox(height: 12));
      body.add(FilledButton.icon(
        style: FilledButton.styleFrom(minimumSize: const Size(0, 48)),
        onPressed: aiBusy ? null : onAi,
        icon: aiBusy
            ? const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.auto_awesome, size: 18),
        label: Text(aiBusy ? 'AI 生成中…' : 'AI 生成解析'),
      ));
    }

    if (tags.isNotEmpty) {
      body.add(const SizedBox(height: 12));
      body.add(Wrap(
        spacing: 6,
        runSpacing: 6,
        children: tags
            .map((String t) => AppBadge(t, tone: BadgeTone.info))
            .toList(),
      ));
    }

    return AppCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: body,
      ),
    );
  }
}
