import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import '../../widgets/widgets.dart';
import '../quiz/option_tile.dart';

/// 背卡关联源题浏览页：左右滑动/按钮切换，返回时回到背卡原位置。
class SourceQuestionsPage extends StatefulWidget {
  final List<SourceQuestion> list;
  final int start;
  const SourceQuestionsPage({super.key, required this.list, this.start = 0});

  @override
  State<SourceQuestionsPage> createState() => _SourceQuestionsPageState();
}

class _SourceQuestionsPageState extends State<SourceQuestionsPage> {
  late final PageController _ctl =
      PageController(initialPage: widget.start);
  late int _idx = widget.start;
  List<Question>? _qs;
  Object? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final List<Question> r = await Endpoints.questions(
          QuizQuery(ids: widget.list.map((SourceQuestion e) => e.id).toList()));
      if (!mounted) return;
      setState(() => _qs = r);
    } catch (e) {
      if (!mounted) return;
      setState(() => _err = e);
    }
  }

  Question? _find(int id) {
    final List<Question>? qs = _qs;
    if (qs == null) return null;
    for (final Question q in qs) {
      if (q.id == id) return q;
    }
    return null;
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('源题 ${_idx + 1} / ${widget.list.length}'),
      ),
      body: _err != null
          ? LoadError(msg: errText(_err!), onRetry: () {
              setState(() => _err = null);
              _load();
            })
          : _qs == null
              ? const LoadingView()
              : PageView.builder(
                  controller: _ctl,
                  itemCount: widget.list.length,
                  onPageChanged: (int i) => setState(() => _idx = i),
                  itemBuilder: (BuildContext ctx, int i) {
                    final SourceQuestion src = widget.list[i];
                    final Question? q = _find(src.id);
                    return _SourceBody(src: src, q: q);
                  },
                ),
      bottomNavigationBar: widget.list.length > 1
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: Row(
                  children: <Widget>[
                    FilledButton.tonal(
                      onPressed: _idx > 0
                          ? () => _ctl.previousPage(
                              duration: const Duration(milliseconds: 180),
                              curve: Curves.easeOut)
                          : null,
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Icon(Icons.chevron_left, size: 18),
                          Text('上一题'),
                        ],
                      ),
                    ),
                    const Spacer(),
                    FilledButton.tonal(
                      onPressed: _idx < widget.list.length - 1
                          ? () => _ctl.nextPage(
                              duration: const Duration(milliseconds: 180),
                              curve: Curves.easeOut)
                          : null,
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Text('下一题'),
                          Icon(Icons.chevron_right, size: 18),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )
          : null,
    );
  }
}

class _SourceBody extends StatelessWidget {
  final SourceQuestion src;
  final Question? q;
  const _SourceBody({required this.src, required this.q});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final AppColors c = AppColors.of(context);
    final Question? qq = q;
    final String analysis =
        (qq != null && qq.analysisHtml.isNotEmpty) ? qq.analysisHtml : src.analysisHtml;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: <Widget>[
        Wrap(
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: <Widget>[
            if (qq != null && qq.qtype.isNotEmpty)
              AppBadge(qq.qtype, tone: BadgeTone.primary),
            AppBadge(src.system),
            if (qq != null && qq.chapter.isNotEmpty) AppBadge(qq.chapter),
            Text(src.qid,
                style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
          ],
        ),
        const SizedBox(height: 10),
        if (qq != null && qq.parentHtml.isNotEmpty) ...<Widget>[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHighest.withOpacity(0.5),
              border: Border(left: BorderSide(color: cs.primary, width: 3)),
            ),
            child: HtmlView(qq.parentHtml),
          ),
          const SizedBox(height: 10),
        ],
        HtmlView(qq != null && qq.stemHtml.isNotEmpty ? qq.stemHtml : src.stemHtml),
        if (qq != null && qq.optionsHtml.isNotEmpty) ...<Widget>[
          const SizedBox(height: 10),
          OptionList(
            q: qq,
            picked: '',
            judged: true,
            reveal: true,
            stat: null,
            onPick: (_) {},
          ),
        ],
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: c.goodSoft,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text.rich(TextSpan(children: <InlineSpan>[
            const TextSpan(text: '正确答案 '),
            TextSpan(
              text: qq != null && qq.answer.isNotEmpty ? qq.answer : src.answer,
              style: TextStyle(
                  fontWeight: FontWeight.w800, fontSize: 16, color: c.good),
            ),
          ])),
        ),
        const SizedBox(height: 12),
        Text('解析',
            style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: cs.onSurfaceVariant)),
        const SizedBox(height: 4),
        HtmlView(analysis.isEmpty ? '<p>本题暂无解析</p>' : analysis),
      ],
    );
  }
}
