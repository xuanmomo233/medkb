import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api.dart';
import '../widgets.dart';
import '../main.dart';
import 'quiz.dart';
import 'cards.dart';
import 'notes.dart';

/// 今日：倒计时 + 打卡 + 目标 + 日历 + 到期/错题/收藏
class TodayPage extends StatefulWidget {
  const TodayPage({super.key});
  @override
  State<TodayPage> createState() => _TodayState();
}

class _TodayState extends State<TodayPage> {
  Map<String, dynamic> stats = {};
  Map<String, dynamic> today = {};
  Map<String, dynamic> plan = {};
  List<dynamic> calDays = [];
  DateTime calYm = DateTime(DateTime.now().year, DateTime.now().month);

  bool _err = false;
  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      stats = await Api.get('/api/stats', cache: false);
      today = await Api.get('/api/today', cache: false);
      plan = await Api.get('/api/plan', cache: false);
      await _loadCal();
      _err = false;
    } catch (_) { _err = true; }
    if (mounted) setState(() {});
  }
  Future<void> _loadCal() async {
    try {
      final ym = '${calYm.year}-${calYm.month.toString().padLeft(2, '0')}';
      final c = await Api.get('/api/calendar?ym=$ym', cache: false);
      calDays = c['days'] ?? [];
    } catch (_) {}
  }

  List<int> _refs(List l, String kind) => l
      .where((x) => x['kind'] == kind)
      .map<int>((x) => int.parse(x['ref'].toString())).toList();

  void _open(String kind, List<int> ids) {
    if (ids.isEmpty) return;
    final page = kind == 'q'
        ? QuizListPage(ids: ids)
        : CardRunPage(ids: ids);
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final pri = Theme.of(context).colorScheme.primary;
    final qDue = _refs(today['due'] ?? [], 'q');
    final kDue = _refs(today['due'] ?? [], 'k');
    final qWrong = _refs(today['wrong'] ?? [], 'q');
    final kWrong = _refs(today['wrong'] ?? [], 'k');
    final qStar = _refs(today['starred'] ?? [], 'q');
    final kStar = _refs(today['starred'] ?? [], 'k');
    final goal = today['goal'] ?? 30;
    final done = today['done_today'] ?? 0;
    return Scaffold(
      appBar: AppBar(
        title: const Text('今日'),
        actions: [
          Center(child: Padding(
            padding: const EdgeInsets.only(right: 4),
            child: InkWell(
              onTap: () async {
                try {
                  final v = await Api.checkUpdate();
                  if (!context.mounted) return;
                  if (v == null) {
                    toast(context, '已是最新版（build ${Api.appBuild}）');
                  } else {
                    showDialog(context: context, builder: (_) => AlertDialog(
                      title: const Text('发现新版本'),
                      content: Text('${v['note']}\n'
                          '（当前 build ${Api.appBuild} → ${v['build']}）'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context),
                            child: const Text('稍后')),
                        FilledButton(onPressed: () {
                          launchUrl(Uri.parse('${Api.base}/app.apk'),
                              mode: LaunchMode.externalApplication);
                          Navigator.pop(context);
                        }, child: const Text('去更新')),
                      ]));
                  }
                } catch (_) {
                  toast(context, '检查更新失败');
                }
              },
              child: Text('build ${Api.appBuild} ↻',
                  style: TextStyle(fontSize: 11,
                      color: Theme.of(context).colorScheme.outline))))),
          IconButton(icon: const Icon(Icons.format_size, size: 20),
              onPressed: () => showFontSheet(context)),
          IconButton(icon: const Icon(Icons.settings_outlined, size: 20),
              onPressed: () => _settingsSheet(context)),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ]),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(padding: const EdgeInsets.all(14), children: [
          if (_err)
            Card(color: Theme.of(context).colorScheme.errorContainer,
              child: ListTile(
                leading: const Icon(Icons.cloud_off_outlined),
                title: const Text('数据加载失败', style: TextStyle(fontSize: 14)),
                subtitle: const Text('下拉或点按重试',
                    style: TextStyle(fontSize: 12)),
                onTap: _load)),
          // ===== 倒计时 + 打卡 + 目标 =====
          Row(children: [
            Expanded(child: _bCard(
              '考研倒计时', '${today['exam_days'] ?? '—'}', '天', pri,
              sub: today['exam_date'] ?? '',
              onTap: _setExam)),
            const SizedBox(width: 8),
            Expanded(child: _bCard(
              '连续打卡', '${today['streak'] ?? 0}', '天', const Color(0xFFF59E0B),
              sub: today['checked_today'] == true ? '✅ 今日已打卡' : '点我打卡',
              onTap: today['checked_today'] == true ? null : _checkin)),
            const SizedBox(width: 8),
            Expanded(child: _bCard(
              '今日学习', '$done', '/ $goal 条', const Color(0xFF16A34A),
              sub: '修改目标', onTap: _setGoal)),
          ]),
          const SizedBox(height: 8),
          ClipRRect(borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: goal > 0 ? (done / goal).clamp(0.0, 1.0) : 0,
              minHeight: 8, backgroundColor: Colors.grey.withOpacity(0.2))),
          const SizedBox(height: 14),
          _planCard(),
          // ===== 打卡日历 =====
          Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(children: [
            Row(children: [
              const Text('📅 打卡日历', style: TextStyle(fontWeight: FontWeight.w700)),
              const Spacer(),
              IconButton(visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.chevron_left),
                  onPressed: () {
                    setState(() { calYm = DateTime(calYm.year, calYm.month - 1); _loadCal(); });
                  }),
              Text('${calYm.year}年${calYm.month}月',
                  style: const TextStyle(fontSize: 13)),
              IconButton(visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.chevron_right),
                  onPressed: () {
                    setState(() { calYm = DateTime(calYm.year, calYm.month + 1); _loadCal(); });
                  }),
            ]),
            _calGrid(),
          ]))),
          const SizedBox(height: 14),
          // ===== 统计 =====
          Row(children: [
            _stat('题目', '${stats['questions'] ?? '-'}'),
            _stat('考点', '${stats['kp_items'] ?? '-'}'),
            _stat('章节', '${stats['chapters'] ?? '-'}'),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            _stat('已掌握', '${stats['mastered'] ?? '-'}',
                c: const Color(0xFF16A34A)),
            _stat('错题', '${stats['wrong'] ?? '-'}',
                c: const Color(0xFFDC2626)),
            _stat('收藏', '${stats['starred'] ?? '-'}',
                c: const Color(0xFFF59E0B)),
          ]),
          const SizedBox(height: 14),
          _group('⏰ 到期复习', '${qDue.length + kDue.length}', [
            if (qDue.isNotEmpty)
              _run('刷题 ${qDue.length} 题', () => _open('q', qDue)),
            if (kDue.isNotEmpty)
              _run('背卡 ${kDue.length} 张', () => _open('k', kDue)),
          ]),
          _group('❌ 错题本', '${qWrong.length + kWrong.length}', [
            if (qWrong.isNotEmpty)
              _run('刷题 ${qWrong.length} 题', () => _open('q', qWrong)),
            if (kWrong.isNotEmpty)
              _run('背卡 ${kWrong.length} 张', () => _open('k', kWrong)),
          ]),
          _group('⭐ 收藏夹', '${qStar.length + kStar.length}', [
            if (qStar.isNotEmpty)
              _run('刷题 ${qStar.length} 题', () => _open('q', qStar)),
            if (kStar.isNotEmpty)
              _run('背卡 ${kStar.length} 张', () => _open('k', kStar)),
          ]),
          _group('📝 我的笔记', '', [
            _run('查看全部笔记', () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const NotesPage()))),
          ]),
        ]),
      ),
    );
  }

  /// 10天内外科学习计划卡（服务端排定课表 + 当天背卡/针对出题）
  Widget _planCard() {
    if (plan.isEmpty) return const SizedBox();
    final pri = Theme.of(context).colorScheme.primary;
    final kids = (plan['kids'] as List? ?? [])
        .map<int>((x) => int.parse(x.toString())).toList();
    final qids = (plan['qids'] as List? ?? [])
        .map<int>((x) => int.parse(x.toString())).toList();
    if (plan['finished'] == true) {
      return Card(child: Padding(padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('📋 10天内外科计划',
              style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          const Text('🎉 计划已完成', style: TextStyle(color: Color(0xFF16A34A))),
          TextButton(onPressed: () async {
            try {
              await Api.post('/api/plan/restart', {});
              _load();
            } catch (_) {
              if (context.mounted) toast(context, '操作失败，请检查网络');
            }
          }, child: const Text('重新开始一轮')),
        ])));
    }
    final tot = kids.length + qids.length;
    final dn = (plan['kdone'] ?? 0) + (plan['qdone'] ?? 0);
    return Card(child: Padding(padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text('📋 10天内外科冲刺 · 第${plan['today_no']}/${plan['days']}天',
              style: const TextStyle(fontWeight: FontWeight.w700)),
          const Spacer(),
          InkWell(onTap: () async {
            final ok = await showDialog<bool>(context: context,
              builder: (_) => AlertDialog(
                title: const Text('重新排期'),
                content: const Text('从今天开始重新计为第 1 天？'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(context, false),
                      child: const Text('取消')),
                  FilledButton(onPressed: () => Navigator.pop(context, true),
                      child: const Text('重排')),
                ]));
            if (ok == true) {
              try {
                await Api.post('/api/plan/restart', {});
                _load();
              } catch (_) {
                if (context.mounted) toast(context, '操作失败，请检查网络');
              }
            }
          }, child: const Text('重排', style: TextStyle(
              fontSize: 12, color: Colors.grey))),
        ]),
        const SizedBox(height: 4),
        Text(plan['label'] ?? '', style: const TextStyle(
            fontSize: 15, fontWeight: FontWeight.w600)),
        Text('今日进度 $dn/$tot（背卡 ${plan['kdone']}/${kids.length}'
            ' · 刷题 ${plan['qdone']}/${qids.length}）',
            style: const TextStyle(fontSize: 12, color: Colors.grey)),
        const SizedBox(height: 6),
        ClipRRect(borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: tot > 0 ? (dn / tot).clamp(0.0, 1.0) : 0,
            minHeight: 6, backgroundColor: Colors.grey.withOpacity(0.2),
            color: pri)),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 6, children: [
          FilledButton.icon(icon: const Icon(Icons.style, size: 16),
            label: Text('背卡 ${kids.length}'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => CardRunPage(plan: plan['today_no'] as int?)))),
          FilledButton.tonalIcon(icon: const Icon(Icons.quiz, size: 16),
            label: Text('针对出题 ${qids.length}'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => QuizListPage(plan: plan['today_no'] as int?)))),
        ]),
        const SizedBox(height: 8),
        Wrap(spacing: 4, children: [
          for (final d in (plan['overview'] as List? ?? []))
            Semantics(
              button: true,
              label: '第 ${d['no']} 天${(d['no'] as int) < (plan['today_no'] as int? ?? 0) ? '，已完成' : d['no'] == plan['today_no'] ? '，今天' : ''}',
              onTap: () => _openDay(d['no'] as int),
              child: GestureDetector(
              onTap: () => _openDay(d['no'] as int),
              child: Container(width: 22, height: 22,
                decoration: BoxDecoration(
                  color: d['no'] == plan['today_no'] ? pri
                      : (d['no'] as int) < (plan['today_no'] as int? ?? 0)
                          ? const Color(0xFF16A34A)
                          : Colors.grey.withOpacity(0.25),
                  borderRadius: BorderRadius.circular(11)),
                child: Center(child: Text('${d['no']}',
                    style: TextStyle(fontSize: 11,
                        color: (d['no'] == plan['today_no'] ||
                                (d['no'] as int) < (plan['today_no'] as int? ?? 0))
                            ? Colors.white : Colors.black54)))))),
        ]),
        const SizedBox(height: 2),
        const Text('点日期可展开挑选内容', style: TextStyle(fontSize: 10, color: Colors.grey)),
      ])));
  }

  /// 点开计划某天：卡片清单（点单张看）+ 题集按章节分组（点章节刷）
  Future<void> _openDay(int no) async {
    Map<String, dynamic> d;
    try {
      d = await Api.get('/api/plan/day?n=$no', cache: false);
    } catch (_) {
      if (mounted) toast(context, '加载失败');
      return;
    }
    if (!mounted) return;
    final cards = (d['cards'] as List? ?? []);
    final qg = (d['qg'] as List? ?? []);
    showModalBottomSheet(context: context, isScrollControlled: true,
      builder: (_) => SafeArea(child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('第${d['no']}天 · ${d['label']}',
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: FilledButton.icon(
              icon: const Icon(Icons.style, size: 16),
              label: Text('背全部卡 ${cards.length}'),
              onPressed: () {
                Navigator.pop(context);
                Navigator.push(context, MaterialPageRoute(
                    builder: (_) => CardRunPage(ids: cards.map<int>(
                        (c) => c['id'] as int).toList())));
              })),
            const SizedBox(width: 8),
            if (qg.isNotEmpty)
              Expanded(child: FilledButton.tonalIcon(
                icon: const Icon(Icons.quiz, size: 16),
                label: Text('刷全部题 ${qg.fold<int>(0,
                    (s, g) => s + (g['ids'] as List).length)}'),
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.push(context, MaterialPageRoute(
                      builder: (_) => QuizListPage(ids: [
                        for (final g in qg)
                          ...(g['ids'] as List).map<int>(
                              (x) => x as int)])));
                })),
          ]),
          const SizedBox(height: 10),
          Flexible(child: ListView(shrinkWrap: true, children: [
            if (cards.isNotEmpty) ...[
              const Text('📖 卡片清单',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
              for (final c in cards)
                ListTile(dense: true, visualDensity: VisualDensity.compact,
                  title: Text(c['term'] ?? '',
                      style: const TextStyle(fontSize: 13)),
                  subtitle: Text(c['part'] ?? '',
                      style: const TextStyle(fontSize: 11)),
                  onTap: () {
                    Navigator.pop(context);
                    Navigator.push(context, MaterialPageRoute(
                        builder: (_) => CardRunPage(ids: [c['id'] as int])));
                  }),
            ],
            if (qg.isNotEmpty) ...[
              const Padding(padding: EdgeInsets.only(top: 8),
                child: Text('📝 按章节刷题',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
              Wrap(spacing: 6, runSpacing: 4, children: [
                for (final g in qg)
                  ActionChip(
                    label: Text('${g['chapter']} ${(g['ids'] as List).length}',
                        style: const TextStyle(fontSize: 12)),
                    onPressed: () {
                      Navigator.pop(context);
                      Navigator.push(context, MaterialPageRoute(
                          builder: (_) => QuizListPage(ids: [
                            for (final x in (g['ids'] as List))
                              x as int])));
                    }),
              ]),
            ],
          ])),
        ]))));
  }

  Widget _calGrid() {
    final marked = calDays.map((d) => int.parse(d.toString())).toSet();
    final first = DateTime(calYm.year, calYm.month, 1).weekday % 7;
    final dim = DateTime(calYm.year, calYm.month + 1, 0).day;
    final todayD = DateTime.now().day;
    final isCur = calYm.year == DateTime.now().year && calYm.month == DateTime.now().month;
    final cells = <Widget>[];
    for (final d in '日一二三四五六'.split('')) {
      cells.add(Center(child: Text(d,
          style: const TextStyle(fontSize: 11, color: Colors.grey))));
    }
    for (var i = 0; i < first; i++) { cells.add(const SizedBox()); }
    for (var d = 1; d <= dim; d++) {
      final on = marked.contains(d);
      final isToday = isCur && d == todayD;
      cells.add(Container(
        margin: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          color: on ? Theme.of(context).colorScheme.primary : null,
          borderRadius: BorderRadius.circular(8),
          border: isToday && !on
              ? Border.all(color: Theme.of(context).colorScheme.primary) : null,
        ),
        child: Center(child: Text('$d', style: TextStyle(fontSize: 12,
            fontWeight: on ? FontWeight.w700 : FontWeight.w400,
            color: on ? Colors.white : null))),
      ));
    }
    return GridView.count(crossAxisCount: 7, shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1.4, children: cells);
  }

  Future<void> _checkin() async {
    try {
      final j = await Api.post('/api/checkin', {});
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('🔥 打卡成功！连续 ${j['streak']} 天')));
      _load();
    } catch (_) {
      if (context.mounted) toast(context, '打卡失败，请检查网络');
    }
  }

  Future<void> _setGoal() async {
    final c = TextEditingController(text: '${today['goal'] ?? 30}');
    final v = await showDialog<int>(context: context, builder: (_) => AlertDialog(
      title: const Text('每日学习目标'),
      content: TextField(controller: c, keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: '每天评分条数')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(onPressed: () => Navigator.pop(context, int.tryParse(c.text)),
            child: const Text('确定')),
      ]));
    if (v != null) {
      try {
        await Api.post('/api/goal', {'target': v});
        _load();
      } catch (_) {
        if (context.mounted) toast(context, '保存失败，请检查网络');
      }
    }
  }

  Future<void> _setExam() async {
    final c = TextEditingController(text: today['exam_date'] ?? '2026-12-19');
    final v = await showDialog<String>(context: context, builder: (_) => AlertDialog(
      title: const Text('考研日期'),
      content: TextField(controller: c,
          decoration: const InputDecoration(labelText: 'YYYY-MM-DD')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(onPressed: () => Navigator.pop(context, c.text),
            child: const Text('确定')),
      ]));
    if (v != null && v.isNotEmpty) {
      try {
        await Api.post('/api/exam', {'date': v});
        _load();
      } catch (_) {
        if (context.mounted) toast(context, '保存失败，请检查网络');
      }
    }
  }

  void _settingsSheet(BuildContext context) {
    showModalBottomSheet(context: context, builder: (_) => SafeArea(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ListTile(leading: const Icon(Icons.cached),
          title: const Text('本地缓存'),
          subtitle: FutureBuilder<int>(
            future: Api.cacheBytes(),
            builder: (_, s) => Text(
                '${((s.data ?? 0) / 1048576).toStringAsFixed(1)} MB（离线可读已看过的内容）')),
          trailing: TextButton(
            onPressed: () async {
              await Api.cacheClear();
              if (context.mounted) Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('缓存已清理')));
            },
            child: const Text('清理'))),
        ListTile(leading: const Icon(Icons.format_size),
          title: const Text('正文字号'),
          onTap: () { Navigator.pop(context); showFontSheet(context); }),
        ListTile(leading: const Icon(Icons.logout),
          title: const Text('退出登录'),
          onTap: () async {
            try { await Api.post('/api/logout', {}); } catch (_) {}
            // 清 token + 本账号缓存，防下一位登录者看到旧数据
            await Api.clearSession();
            if (context.mounted) {
              Navigator.pop(context);
              runApp(const App());
            }
          }),
      ]),
    ));
  }

  Widget _bCard(String label, String big, String unit, Color c,
      {String sub = '', VoidCallback? onTap}) => InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Card(child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        child: Column(children: [
          RichText(text: TextSpan(children: [
            TextSpan(text: big, style: TextStyle(fontSize: 24,
                fontWeight: FontWeight.w800, color: c)),
            TextSpan(text: ' $unit', style: TextStyle(fontSize: 11, color: c)),
          ])),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 11.5)),
          Text(sub, style: const TextStyle(fontSize: 10.5, color: Colors.grey)),
        ]),
      )),
    );

  Widget _stat(String label, String v, {Color? c}) => Expanded(
        child: Card(child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Column(children: [
            Text(v, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800,
                color: c)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(fontSize: 12)),
          ]),
        )),
      );

  Widget _group(String title, String n, List<Widget> btns) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Card(child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
              const Spacer(),
              Text(n, style: TextStyle(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w700)),
            ]),
            if (btns.isEmpty)
              const Padding(padding: EdgeInsets.only(top: 8),
                  child: Text('（空）', style: TextStyle(fontSize: 12,
                      color: Colors.grey)))
            else
              Padding(padding: const EdgeInsets.only(top: 8),
                child: Wrap(spacing: 8, runSpacing: 8, children: btns)),
          ]),
        )),
      );

  Widget _run(String label, VoidCallback f) => OutlinedButton(
      onPressed: f, child: Text(label));
}
