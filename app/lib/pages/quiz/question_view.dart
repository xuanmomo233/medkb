import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'analysis_panel.dart';
import 'option_tile.dart';
import 'question_toolbar.dart';
import 'quiz_session.dart';

class QuestionPageView extends StatelessWidget {
  final QuizSession s;
  final int index;
  const QuestionPageView({super.key, required this.s, required this.index});

  @override
  Widget build(BuildContext context) {
    final Question q = s.questions[index];
    final ColorScheme cs = Theme.of(context).colorScheme;
    final Ans? cur = s.ans[q.id];
    final bool judged = cur?.judged ?? false;
    final bool hasOpt = hasOptionsQ(q);
    final bool hide = s.isRecite && s.hidden.contains(q.id);
    final bool reveal = judged || (s.isRecite && !hide);
    final bool showAnalysis = s.showFull(q) && !hide;
    final bool multi = isMultiQ(q);
    final bool addMulti =
        multi && !q.qtype.contains('多') && !q.qtype.contains('X');

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: <Widget>[
        Wrap(
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: <Widget>[
            AppBadge('${q.qtype}${addMulti ? '（多选）' : ''}',
                tone: BadgeTone.primary),
            if (q.system.isNotEmpty) AppBadge(q.system),
            if (q.chapter.isNotEmpty) AppBadge(q.chapter),
            Text(q.qid,
                style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
          ],
        ),
        const SizedBox(height: 10),
        if (q.parentHtml.isNotEmpty) ...<Widget>[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: cs.onSurface.withOpacity(0.05),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('共用题干${q.caseTotal > 0 ? ' · ${q.caseTotal} 个子题' : ''}',
                    style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                HtmlView(q.parentHtml),
                if (q.caseGroup.isNotEmpty && q.caseTotal > 1)
                  Wrap(
                    spacing: 6,
                    children: <Widget>[
                      for (int i = 0; i < s.questions.length; i++)
                        if (s.questions[i].caseGroup == q.caseGroup)
                          ChoiceChip(
                            label: Text('子题 ${s.questions[i].caseIndex}${(s.ans[s.questions[i].id]?.picked ?? '').isNotEmpty ? ' · 已答' : ''}'),
                            selected: s.questions[i].id == q.id,
                            onSelected: (_) => s.pageTo?.call(i),
                          ),
                    ],
                  ),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],
        HtmlView(q.stemHtml),
        const SizedBox(height: 14),
        if (hasOpt)
          OptionList(
            q: q,
            picked: cur?.picked ?? '',
            judged: judged,
            reveal: reveal,
            stat: s.statOf(q),
            onPick: (String l) => s.pick(q, l),
          ),
        if (s.isRecite && hide)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text('答案已隐藏，点击底部「显示答案」查看',
                style: TextStyle(color: cs.onSurfaceVariant)),
          ),
        const SizedBox(height: 8),
        QuestionToolbar(
          starred: s.starredOf(q),
          state: s.stateOf(q),
          canRedo: !s.isTest && judged,
          onToggle: (MarkKind k) => s.toggleMark(q, k),
          onRedo: () => s.redo(q),
          onNotes: () => openNotes(context,
              targetType: TargetType.question, targetId: q.id),
          onEdit: () async {
            if (await openAdminEdit(context, q.id)) {
              await s.refreshFull(q.id);
            }
          },
        ),
        if (showAnalysis) ...<Widget>[
          const SizedBox(height: 8),
          AnalysisPanel(
            allowRelated: !s.isTest,
            onPracticed: s.args.planDay != null || s.args.fresh ? s.load : null,
            q: q,
            picked: cur?.picked ?? '',
            judged: judged,
            correct: cur?.correct,
            full: s.full[q.id],
            failed: s.fullErr.contains(q.id),
            stat: s.statOf(q),
            aiBusy: s.aiBusy,
            onRetry: () => s.loadFull(q.id),
            onAi: () => s.genAnalysis(q),
          ),
        ],
      ],
    );
  }
}
