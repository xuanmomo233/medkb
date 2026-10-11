import 'dart:ui' show PathMetric;
import 'package:flutter/material.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import '../../widgets/widgets.dart';
import 'quiz_session.dart';

class OptionList extends StatelessWidget {
  final Question q;
  final String picked;
  final bool judged;
  final bool reveal;
  final QuestionStat? stat;
  final void Function(String letter) onPick;
  const OptionList({
    super.key,
    required this.q,
    required this.picked,
    required this.judged,
    required this.reveal,
    required this.stat,
    required this.onPick,
  });

  @override
  Widget build(BuildContext context) {
    final bool multi = isMultiQ(q);
    final QuestionStat? st = stat;
    int total = 0;
    if (st != null) {
      for (final int v in st.dist.values) {
        total += v;
      }
    }
    final List<Widget> tiles = <Widget>[];
    for (int i = 0; i < q.optionsHtml.length && i < kLetters.length; i++) {
      final String letter = kLetters[i];
      final bool on = picked.contains(letter);
      final bool isAns = reveal && q.answer.contains(letter);
      int? rate;
      if (judged && st != null && total > 0) {
        rate = (((st.dist[letter] ?? 0) * 100) / total).round();
      }
      tiles.add(Padding(
        padding: EdgeInsets.only(top: i == 0 ? 0 : 10),
        child: OptionTile(
          letter: letter,
          html: q.optionsHtml[i],
          multi: multi,
          selected: on,
          isAnswer: isAns,
          wrongPick: judged && on && !q.answer.contains(letter),
          missed: judged && isAns && !on,
          judged: judged,
          rate: rate,
          onTap: judged ? null : () => onPick(letter),
        ),
      ));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: tiles,
    );
  }
}

class OptionTile extends StatelessWidget {
  final String letter;
  final String html;
  final bool multi;
  final bool selected;
  final bool isAnswer;
  final bool wrongPick;
  final bool missed;
  final bool judged;
  final int? rate;
  final VoidCallback? onTap;
  const OptionTile({
    super.key,
    required this.letter,
    required this.html,
    required this.multi,
    required this.selected,
    required this.isAnswer,
    required this.wrongPick,
    required this.missed,
    required this.judged,
    required this.rate,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors c = AppColors.of(context);
    Color border = cs.outlineVariant;
    Color bg = cs.surface;
    Color iconColor = cs.onSurfaceVariant;
    IconData icon =
        multi ? Icons.check_box_outline_blank : Icons.radio_button_unchecked;
    String tag = '';
    bool dashed = false;
    bool strong = false;
    if (wrongPick) {
      border = c.bad;
      bg = c.badSoft;
      iconColor = c.bad;
      icon = Icons.cancel;
      tag = '你的选择';
      strong = true;
    } else if (missed) {
      border = c.good;
      bg = c.goodSoft.withOpacity(0.45);
      iconColor = c.good;
      icon = Icons.error_outline;
      tag = '漏选';
      dashed = true;
    } else if (isAnswer) {
      border = c.good;
      bg = c.goodSoft;
      iconColor = c.good;
      icon = Icons.check_circle;
      tag = selected ? '选对' : '';
      strong = true;
    } else if (selected) {
      border = cs.primary;
      bg = cs.primary.withOpacity(0.10);
      iconColor = cs.primary;
      icon = multi ? Icons.check_box : Icons.radio_button_checked;
      strong = true;
    }
    final Color letterBg = (wrongPick || isAnswer || selected)
        ? border
        : cs.onSurface.withOpacity(0.08);
    final Color letterFg = (wrongPick || isAnswer || selected)
        ? cs.surface
        : cs.onSurfaceVariant;
    final int? r = rate;

    return Material(
      color: bg,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: dashed
            ? BorderSide.none
            : BorderSide(color: border, width: strong ? 1.8 : 1),
      ),
      child: InkWell(
        onTap: onTap,
        child: CustomPaint(
          foregroundPainter: dashed ? _DashedPainter(border, 12) : null,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 52),
            child: Stack(
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 10, 13),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Container(
                        width: 28,
                        height: 28,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                            color: letterBg, shape: BoxShape.circle),
                        child: Text(letter,
                            style: TextStyle(
                                color: letterFg,
                                fontWeight: FontWeight.w700,
                                fontSize: 13)),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: HtmlView(html)),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: <Widget>[
                          Icon(icon, size: 22, color: iconColor),
                          if (tag.isNotEmpty)
                            Text(tag,
                                style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w600,
                                    color: iconColor)),
                          if (r != null)
                            Text('$r%',
                                style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w600,
                                    color: isAnswer
                                        ? c.good
                                        : (wrongPick
                                            ? c.bad
                                            : cs.onSurfaceVariant))),
                        ],
                      ),
                    ],
                  ),
                ),
                if (r != null)
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: FractionallySizedBox(
                      widthFactor: r / 100,
                      alignment: Alignment.centerLeft,
                      child: Container(
                        height: 4,
                        color: isAnswer
                            ? c.good
                            : (wrongPick
                                ? c.bad
                                : cs.outline.withOpacity(0.5)),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DashedPainter extends CustomPainter {
  final Color color;
  final double radius;
  const _DashedPainter(this.color, this.radius);

  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8;
    final RRect rr = RRect.fromRectAndRadius(
        Offset.zero & size, Radius.circular(radius));
    final Path path = Path()..addRRect(rr.deflate(1));
    for (final PathMetric m in path.computeMetrics()) {
      double d = 0;
      while (d < m.length) {
        canvas.drawPath(m.extractPath(d, d + 6), paint);
        d += 10;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedPainter old) =>
      old.color != color || old.radius != radius;
}
