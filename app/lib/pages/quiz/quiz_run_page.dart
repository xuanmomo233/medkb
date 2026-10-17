import 'package:flutter/material.dart';
import '../../api.dart';
import '../../models.dart' hide Card;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';
import 'exam_report_page.dart';
import 'jump_grid.dart';
import 'question_view.dart';
import 'quiz_session.dart';
import '../today/schedule_navigation.dart';

class QuizRunPage extends StatefulWidget {
  final QuizRunArgs args;
  const QuizRunPage(this.args, {super.key});

  @override
  State<QuizRunPage> createState() => _QuizRunPageState();
}

class _QuizRunPageState extends State<QuizRunPage> {
  late final QuizSession _s;
  PageController? _pc;

  @override
  void initState() {
    super.initState();
    _s = QuizSession(widget.args, _msg);
    _s.pageTo = _animateTo;
    _s.onTimeUp = _autoSubmit;
    _s.load();
  }

  @override
  void dispose() {
    _pc?.dispose();
    _s.dispose();
    super.dispose();
  }

  void _msg(String m) {
    if (mounted) toast(context, m);
  }

  void _animateTo(int i) {
    final PageController? pc = _pc;
    if (pc == null || !pc.hasClients) return;
    pc.animateToPage(i,
        duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
  }

  void _jumpTo(int i) {
    final PageController? pc = _pc;
    if (pc == null || !pc.hasClients) return;
    pc.jumpToPage(i);
  }

  Future<void> _openJump() async {
    final int? i = await showAppSheet<int>(
      context,
      title: '题号跳转',
      builder: (BuildContext ctx) => JumpGrid(
        questions: _s.questions,
        ans: _s.ans,
        idx: _s.idx,
        isTest: _s.isTest,
      ),
    );
    if (i != null && mounted) _jumpTo(i);
  }

  Future<void> _confirmSubmit() async {
    final int un = _s.questions.length - _s.answeredCount;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: const Text('确认交卷'),
        content: Text(un > 0
            ? '还有 $un 题未作答，未答题按错误计分。\n确定现在交卷吗？'
            : '所有题目均已作答，确定现在交卷吗？'),
        actions: <Widget>[
          TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('继续答题')),
          FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('确认交卷')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _doSubmit();
  }

  Future<void> _doSubmit() async {
    final ExamReport? r = await _s.submit();
    if (r == null || !mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
        builder: (BuildContext _) => ExamReportPage(r, _s.title)));
  }

  void _autoSubmit() {
    if (!mounted) return;
    final ModalRoute<dynamic>? route = ModalRoute.of(context);
    if (route != null) {
      Navigator.of(context).popUntil((Route<dynamic> r) => r == route);
    }
    toast(context, '时间到，已自动交卷');
    _doSubmit();
  }

  String _fmt(int sec) {
    final int h = sec ~/ 3600;
    final String m = ((sec % 3600) ~/ 60).toString().padLeft(2, '0');
    final String r = (sec % 60).toString().padLeft(2, '0');
    return h > 0 ? '$h:$m:$r' : '$m:$r';
  }

  String get _modeLabel {
    switch (widget.args.mode) {
      case QuizMode.recite:
        return '背题';
      case QuizMode.quick:
        return '快刷';
      case QuizMode.test:
        return '测试';
      default:
        return '练习';
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(animation: _s, builder: _buildBody);
  }

  Widget _buildBody(BuildContext context, Widget? _) {
    final int total = _s.questions.length;
    final bool ready = _s.status == RunStatus.ready && total > 0;
    final String t = (widget.args.title ?? '').isEmpty
        ? _modeLabel
        : widget.args.title!;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(t, maxLines: 1, overflow: TextOverflow.ellipsis),
            if (ready && _s.isTest)
              Text('已答 ${_s.answeredCount}/$total',
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                      color: Theme.of(context).colorScheme.onSurfaceVariant)),
          ],
        ),
        actions: <Widget>[
          if (ready && _s.isTest)
            ValueListenableBuilder<int?>(
              valueListenable: _s.remaining,
              builder: (BuildContext c, int? v, Widget? _) {
                if (v == null) return const SizedBox.shrink();
                final AppColors col = AppColors.of(c);
                return Row(
                  children: <Widget>[
                    Icon(Icons.timer_outlined,
                        size: 15, color: v < 300 ? col.bad : null),
                    const SizedBox(width: 3),
                    Text(_fmt(v),
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: v < 300 ? col.bad : null)),
                  ],
                );
              },
            ),
          if (ready)
            TextButton.icon(
              style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
              onPressed: _openJump,
              icon: const Icon(Icons.grid_view, size: 18),
              label: Text('${_s.idx + 1}/$total'),
            ),
          if (ready && !_s.isTest)
            TextButton(onPressed: () async {
              await _s.resetSession();
              if (mounted) _jumpTo(0);
            }, child: const Text('本次重练')),
          const SizedBox(width: 4),
        ],
      ),
      body: Column(children: <Widget>[
        if (widget.args.scheduleItems.isNotEmpty)
          ScheduleNavigation(items: widget.args.scheduleItems, index: widget.args.scheduleIndex),
        Expanded(child: _content(context, ready, total)),
      ]),
    );
  }

  Widget _content(BuildContext context, bool ready, int total) {
    if (_s.status == RunStatus.loading) return const LoadingView();
    if (_s.status == RunStatus.error) {
      return LoadError(
          msg: _s.error == null ? '加载失败' : errText(_s.error!),
          onRetry: _s.load);
    }
    if (!ready) {
      return EmptyState(widget.args.planDay != null ? '本批计划题目已完成' : '没有符合条件的题目',
          action: OutlinedButton(
              onPressed: () => Navigator.of(context).maybePop(),
              child: const Text('返回')));
    }
    final PageController pc = _pc ??= PageController(initialPage: _s.idx);
    final int? resume = _s.resumeAt;
    return Column(
      children: <Widget>[
        ProgressBar(value: (_s.idx + 1) / total, height: 3),
        if (resume != null) _resumeBar(context, resume),
        Expanded(
          child: PageView.builder(
            controller: pc,
            itemCount: total,
            onPageChanged: _s.onPage,
            itemBuilder: (BuildContext c, int i) => QuestionPageView(
              key: ValueKey<int>(_s.questions[i].id),
              s: _s,
              index: i,
            ),
          ),
        ),
        _bottomBar(context, total),
      ],
    );
  }

  Widget _resumeBar(BuildContext context, int resume) {
    final AppColors c = AppColors.of(context);
    return Container(
      color: c.infoSoft,
      padding: const EdgeInsets.fromLTRB(16, 4, 8, 4),
      child: Row(
        children: <Widget>[
          Expanded(
              child: Text('上次做到第 ${resume + 1} 题',
                  style: TextStyle(color: c.info))),
          TextButton(
            style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: () {
              _s.dismissResume();
              _jumpTo(resume);
            },
            child: const Text('跳转'),
          ),
          TextButton(
            style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
            onPressed: _s.dismissResume,
            child: const Text('忽略'),
          ),
        ],
      ),
    );
  }

  Widget _bottomBar(BuildContext context, int total) {
    final Question q = _s.questions[_s.idx];
    final Ans? cur = _s.ans[q.id];
    final bool judged = cur?.judged ?? false;
    final bool multiPending = hasOptionsQ(q) &&
        isMultiQ(q) &&
        !_s.isTest &&
        !_s.isRecite &&
        !judged;
    const Size minSize = Size(0, 48);
    final List<Widget> mid = <Widget>[];
    if (multiPending) {
      mid.add(FilledButton(
        style: FilledButton.styleFrom(minimumSize: minSize),
        onPressed:
            (cur?.picked ?? '').isEmpty ? null : () => _s.confirmMulti(q),
        child: const Text('提交答案'),
      ));
    } else if (_s.isRecite) {
      final bool hide = _s.hidden.contains(q.id);
      mid.add(OutlinedButton(
        style: OutlinedButton.styleFrom(minimumSize: minSize),
        onPressed: () => _s.toggleReveal(q),
        child: Text(hide ? '显示答案' : '隐藏答案'),
      ));
    } else if (_s.isTest) {
      mid.add(FilledButton(
        style: FilledButton.styleFrom(minimumSize: minSize),
        onPressed: _s.submitting ? null : _confirmSubmit,
        child: Text(_s.submitting ? '交卷中…' : '交卷'),
      ));
    }
    final bool last = _s.idx >= total - 1;
    return Material(
      color: Theme.of(context).colorScheme.surface,
      elevation: 4,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
          child: Row(
            children: <Widget>[
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(minimumSize: minSize),
                  onPressed: _s.idx == 0 ? null : () => _animateTo(_s.idx - 1),
                  icon: const Icon(Icons.chevron_left),
                  label: const Text('上一题'),
                ),
              ),
              for (final Widget w in mid) ...<Widget>[
                const SizedBox(width: 8),
                Expanded(child: w),
              ],
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(minimumSize: minSize),
                  onPressed: last
                      ? (widget.args.scheduleItems.isEmpty ? null : () async {
                          try {
                            await nextScheduleItem(context, widget.args.scheduleItems, widget.args.scheduleIndex);
                          } catch (e) {
                            if (mounted) _msg(errText(e));
                          }
                        })
                      : () => _animateTo(_s.idx + 1),
                  icon: const Icon(Icons.chevron_right),
                  label: Text(last && widget.args.scheduleItems.isNotEmpty ? '下一项日程' : '下一题'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
