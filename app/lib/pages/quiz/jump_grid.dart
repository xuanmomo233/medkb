import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import 'quiz_session.dart';

class JumpGrid extends StatelessWidget {
  final List<Question> questions;
  final Map<int, Ans> ans;
  final int idx;
  final bool isTest;
  const JumpGrid({
    super.key,
    required this.questions,
    required this.ans,
    required this.idx,
    required this.isTest,
  });

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors c = AppColors.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Wrap(
            spacing: 14,
            runSpacing: 4,
            children: isTest
                ? <Widget>[
                    _Legend(color: c.infoSoft, text: '已答'),
                    _Legend(color: cs.onSurface.withOpacity(0.08), text: '未答'),
                    _Legend(color: cs.surface, text: '当前', border: c.info),
                  ]
                : <Widget>[
                    _Legend(color: c.goodSoft, text: '✓ 答对'),
                    _Legend(color: c.badSoft, text: '✗ 答错'),
                    _Legend(color: cs.onSurface.withOpacity(0.08), text: '未做'),
                    _Legend(color: cs.surface, text: '当前', border: c.info),
                  ],
          ),
        ),
        Flexible(
          child: GridView.builder(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
            gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 56,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
            ),
            itemCount: questions.length,
            itemBuilder: (BuildContext ctx, int i) {
              final Ans? a = ans[questions[i].id];
              Color bg = cs.onSurface.withOpacity(0.08);
              String mark = '';
              if (isTest) {
                if ((a?.picked ?? '').isNotEmpty) bg = c.infoSoft;
              } else if (a != null && a.judged) {
                if (a.correct == true) {
                  bg = c.goodSoft;
                  mark = '✓';
                } else if (a.correct == false) {
                  bg = c.badSoft;
                  mark = '✗';
                }
              }
              final bool cur = i == idx;
              return InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => Navigator.of(ctx).pop(i),
                child: Container(
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: bg,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: cur ? c.info : Colors.transparent,
                      width: 2,
                    ),
                  ),
                  child: Text(
                    mark.isEmpty ? '${i + 1}' : '${i + 1}$mark',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: cur ? FontWeight.w800 : FontWeight.w500,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _Legend extends StatelessWidget {
  final Color color;
  final String text;
  final Color? border;
  const _Legend({required this.color, required this.text, this.border});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: border ?? Colors.transparent, width: 2),
          ),
        ),
        const SizedBox(width: 4),
        Text(text, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}
