import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart'
    show PlanToday, ScheduleToday, StatsOverview, TodaySummary, WeakSpot;
import '../../nav.dart';
import '../../widgets/widgets.dart';
import 'today_calendar.dart';
import 'today_common.dart';
import 'today_plan.dart';
import 'today_schedule.dart';
import 'today_stats.dart';
import 'today_summary.dart';

class TodayPage extends StatefulWidget {
  const TodayPage({super.key});

  @override
  State<TodayPage> createState() => _TodayPageState();
}

class _TodayPageState extends State<TodayPage> {
  final GlobalKey<AsyncViewState<TodaySummary>> _sumKey =
      GlobalKey<AsyncViewState<TodaySummary>>();
  final GlobalKey<CalendarBlockState> _calKey = GlobalKey<CalendarBlockState>();
  final GlobalKey<AsyncViewState<ScheduleToday>> _schKey =
      GlobalKey<AsyncViewState<ScheduleToday>>();
  final GlobalKey<AsyncViewState<List<WeakSpot>>> _weakKey =
      GlobalKey<AsyncViewState<List<WeakSpot>>>();
  final GlobalKey<AsyncViewState<StatsOverview>> _statKey =
      GlobalKey<AsyncViewState<StatsOverview>>();
  final GlobalKey<AsyncViewState<PlanToday>> _planKey =
      GlobalKey<AsyncViewState<PlanToday>>();

  Future<void> _refreshAll() async {
    await Future.wait(<Future<void>>[
      _sumKey.currentState?.reload() ?? Future<void>.value(),
      _calKey.currentState?.reload() ?? Future<void>.value(),
      _schKey.currentState?.reload() ?? Future<void>.value(),
      _weakKey.currentState?.reload() ?? Future<void>.value(),
      _statKey.currentState?.reload() ?? Future<void>.value(),
      _planKey.currentState?.reload() ?? Future<void>.value(),
    ]);
  }

  void _onReturn() {
    if (mounted) _refreshAll();
  }

  void _onSummaryChanged() {
    _sumKey.currentState?.reload();
    _calKey.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('今日'),
        actions: <Widget>[
          IconButton(
            tooltip: '搜索',
            icon: const Icon(Icons.search),
            onPressed: () => openSearch(context, ''),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refreshAll,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 120),
              child: AsyncView<TodaySummary>(
                key: _sumKey,
                loader: Endpoints.today,
                showCacheBanner: false,
                builder: (BuildContext ctx, TodaySummary d, RefreshFn refresh) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      GreetingBlock(data: d, onReturn: _onReturn),
                      const SizedBox(height: 12),
                      CheckinBlock(data: d, onChecked: _onSummaryChanged),
                      const SizedBox(height: 12),
                      TodoBlock(counts: d.counts, onReturn: _onReturn),
                    ],
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            CalendarBlock(key: _calKey),
            const SizedBox(height: 12),
            asyncBlock<ScheduleToday>(
              key: _schKey,
              title: '今日日程',
              loader: Endpoints.scheduleToday,
              builder: (BuildContext ctx, ScheduleToday d, RefreshFn refresh) =>
                  ScheduleList(
                data: d,
                onReturn: _onReturn,
                onChanged: () => _sumKey.currentState?.reload(),
              ),
            ),
            const SizedBox(height: 12),
            asyncBlock<List<WeakSpot>>(
              key: _weakKey,
              title: '薄弱点分析',
              loader: Endpoints.weakSpots,
              builder: (BuildContext ctx, List<WeakSpot> l, RefreshFn refresh) =>
                  WeakList(list: l, onReturn: _onReturn),
            ),
            const SizedBox(height: 12),
            asyncBlock<StatsOverview>(
              key: _statKey,
              title: '学习统计',
              loader: Endpoints.statsOverview,
              builder: (BuildContext ctx, StatsOverview d, RefreshFn refresh) =>
                  StatsBody(data: d),
            ),
            const SizedBox(height: 12),
            asyncBlock<PlanToday>(
              key: _planKey,
              title: '学习计划',
              loader: Endpoints.plan,
              builder: (BuildContext ctx, PlanToday p, RefreshFn refresh) =>
                  PlanBody(
                plan: p,
                onReturn: _onReturn,
                onRestarted: () => _planKey.currentState?.reload(),
              ),
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}
