import 'package:flutter/material.dart';
import '../../models.dart' show ScheduleItem, TargetType;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import '../quiz/quiz_run_page.dart';
import '../cards/card_run_page.dart';
import 'schedule_navigation.dart';
import 'schedule_session.dart';

class ScheduleRunPage extends StatefulWidget {
  final List<ScheduleItem> items;
  final int initialIndex;
  final String? day;
  const ScheduleRunPage(
      {super.key, required this.items, required this.initialIndex, this.day});

  @override
  State<ScheduleRunPage> createState() => _ScheduleRunPageState();
}

class _ScheduleRunPageState extends State<ScheduleRunPage> {
  late final ScheduleSession _session;
  late final PageController _pages;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _session = ScheduleSession(
        items: widget.items,
        index: widget.initialIndex,
        day: widget.day ?? DateTime.now().toIso8601String().split('T').first);
    _pages = PageController(initialPage: widget.initialIndex);
    _session.onNavigate = _go;
    _session.onOpenJump = () => showScheduleJump(context, _session);
    _load();
  }

  Future<void> _load() async {
    await _session.load();
    if (!mounted) return;
    setState(() => _ready = true);
    _session.start();
  }

  void _go(int index) {
    if (!_pages.hasClients) return;
    if ((index - _session.index).abs() > 1 ||
        MediaQuery.of(context).disableAnimations) {
      _pages.jumpToPage(index);
    } else {
      _pages.animateToPage(index,
          duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    }
  }

  @override
  void dispose() {
    _pages.dispose();
    _session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) return const Scaffold(body: LoadingView());
    return AnimatedBuilder(
        animation: _session,
        builder: (context, _) => PageView.builder(
              controller: _pages,
              itemCount: _session.items.length,
              onPageChanged: _session.setIndex,
              itemBuilder: (context, index) {
                final item = _session.items[index];
                final page = item.itemType == TargetType.question
                    ? QuizRunPage(QuizRunArgs(
                        ids: [item.itemId],
                        title: '今日日程',
                        scheduleItems: _session.items,
                        scheduleIndex: index,
                        scheduleSession: _session))
                    : CardRunPage(CardRunArgs(
                        ids: [item.itemId],
                        scheduleItems: _session.items,
                        scheduleIndex: index,
                        scheduleSession: _session));
                return _StudyPage(
                    key: ValueKey('${item.itemType}:${item.itemId}:${item.id}'),
                    child: page);
              },
            ));
  }
}

class _StudyPage extends StatefulWidget {
  final Widget child;
  const _StudyPage({super.key, required this.child});
  @override
  State<_StudyPage> createState() => _StudyPageState();
}

class _StudyPageState extends State<_StudyPage>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;
  @override
  Widget build(BuildContext context) {
    super.build(context);
    return widget.child;
  }
}
