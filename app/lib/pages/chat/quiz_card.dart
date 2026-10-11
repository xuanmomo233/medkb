import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';

class QuizCard extends StatefulWidget {
  final ChatQuiz quiz;
  final void Function(ChatAnswerResult r) onResult;
  const QuizCard({super.key, required this.quiz, required this.onResult});

  @override
  State<QuizCard> createState() => _QuizCardState();
}

class _QuizCardState extends State<QuizCard> {
  List<String> _picked = <String>[];
  ChatAnswerResult? _result;
  bool _busy = false;

  Future<void> _submit(List<String> keys) async {
    if (_busy || _result != null) return;
    setState(() => _busy = true);
    final List<String> sorted = List<String>.of(keys)..sort();
    try {
      final ChatAnswerResult r =
          await Endpoints.chatAnswer(widget.quiz.qid, sorted.join());
      if (!mounted) return;
      setState(() {
        _result = r;
        _busy = false;
      });
      widget.onResult(r);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      toast(context, errText(e));
    }
  }

  void _pick(String k) {
    if (_busy || _result != null) return;
    if (!widget.quiz.multi) {
      setState(() => _picked = <String>[k]);
      _submit(<String>[k]);
      return;
    }
    setState(() {
      _picked = _picked.contains(k)
          ? _picked.where((String x) => x != k).toList()
          : <String>[..._picked, k];
    });
  }

  Widget _option(ChatQuizOption o) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors ac = AppColors.of(context);
    final ChatAnswerResult? r = _result;
    final bool sel = _picked.contains(o.key);
    Color border = cs.outlineVariant;
    Color? bg;
    Widget? trailing;
    if (r == null) {
      if (sel) {
        border = cs.primary;
        bg = cs.primary.withOpacity(0.10);
      }
    } else if (r.answer.contains(o.key)) {
      border = ac.good;
      bg = ac.goodSoft;
      trailing = Icon(Icons.check_circle, color: ac.good, size: 20);
    } else if (sel) {
      border = ac.bad;
      bg = ac.badSoft;
      trailing = Icon(Icons.cancel, color: ac.bad, size: 20);
    }
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Material(
        color: bg ?? Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: BorderSide(color: border),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: (_busy || r != null) ? null : () => _pick(o.key),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: <Widget>[
                  SizedBox(
                    width: 22,
                    child: Text(o.key,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: sel ? cs.primary : cs.onSurfaceVariant)),
                  ),
                  const SizedBox(width: 6),
                  Expanded(child: HtmlView(o.html)),
                  if (trailing != null) ...<Widget>[
                    const SizedBox(width: 6),
                    trailing,
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ChatQuiz q = widget.quiz;
    final AppColors ac = AppColors.of(context);
    final ChatAnswerResult? r = _result;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const AppBadge('抽背题', tone: BadgeTone.primary),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  '${q.system}${q.multi ? ' · 多选' : ''}',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          HtmlView(q.stemHtml),
          ...q.options.map(_option),
          const SizedBox(height: 6),
          Row(
            children: <Widget>[
              if (r != null)
                Expanded(
                  child: Row(
                    children: <Widget>[
                      Icon(r.correct ? Icons.check_circle : Icons.cancel,
                          size: 18, color: r.correct ? ac.good : ac.bad),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          r.correct ? '回答正确' : '回答错误，正确答案 ${r.answer}',
                          style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: r.correct ? ac.good : ac.bad),
                        ),
                      ),
                    ],
                  ),
                )
              else
                const Spacer(),
              if (q.multi && r == null)
                FilledButton(
                  onPressed:
                      (_picked.isEmpty || _busy) ? null : () => _submit(_picked),
                  child: Text(_busy ? '提交中…' : '提交'),
                ),
              if (!q.qid.startsWith('L'))
                TextButton(
                  onPressed: () => openSearch(context, q.qid),
                  child: const Text('查看原题'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
