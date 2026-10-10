import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'api.dart';
import 'widgets.dart';
import 'pages/login.dart';
import 'pages/browse.dart';
import 'pages/search.dart';
import 'pages/quiz.dart';
import 'pages/cards.dart';
import 'pages/today.dart';
import 'pages/ai_chat.dart';

final navKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Api.load();
  fontScale.value = Api.fontSize;
  // 全局 401：任何页面收到 token 失效 → 清会话 → 回登录页
  Api.onUnauthorized = () {
    Api.pendingAuthMsg = '登录已过期，请重新登录';
    navKey.currentState?.pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const Gate()), (_) => false);
  };
  runApp(const App());
}

class App extends StatelessWidget {
  const App({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '医学知识库',
      navigatorKey: navKey,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2B6CB0),
            brightness: Brightness.light),
        useMaterial3: true,
        cardTheme: CardThemeData(elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Colors.grey.shade200))),
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF4C8FE6),
            brightness: Brightness.dark),
        useMaterial3: true,
      ),
      themeMode: ThemeMode.system,
      home: const Gate(),
    );
  }
}

class Gate extends StatefulWidget {
  const Gate({super.key});
  @override
  State<Gate> createState() => _GateState();
}

class _GateState extends State<Gate> {
  bool? ok;
  bool offline = false;   // 网络不可达但有 token：放行进入离线模式
  @override
  void initState() {
    super.initState();
    _check();
  }
  Future<void> _check() async {
    if (Api.token.isEmpty) { setState(() => ok = false); return; }
    try {
      await Api.get('/api/stats');
      Api.refreshMe();
      if (mounted) setState(() { ok = true; offline = Api.lastFromCache; });
    } on Api401 {
      if (mounted) setState(() => ok = false);
    } on ApiNet {
      // 有 token 但纯网络失败：进入离线模式而非强迫登录
      if (mounted) setState(() { ok = true; offline = true; });
    } catch (_) {
      // HTTP 错误等：服务器可达但异常，同样进离线模式（写操作会真实失败并提示）
      if (mounted) setState(() { ok = true; offline = true; });
    }
  }
  @override
  Widget build(BuildContext context) {
    if (ok == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (ok == false) {
      return LoginPage(onLogin: () => setState(() { ok = true; offline = false; }));
    }
    return HomeShell(onReady: _checkUpdate, offline: offline);
  }

  void _checkUpdate(BuildContext context) async {
    final v = await Api.checkUpdate();
    if (v != null && context.mounted) {
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('发现新版本'),
          content: Text('新版本：${v['note']}\n（当前 build ${Api.appBuild} → 最新 build ${v['build']}）\n建议更新以获得最新功能。'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context),
                child: const Text('稍后')),
            FilledButton(
              onPressed: () {
                launchUrl(Uri.parse('${Api.base}/app.apk'),
                    mode: LaunchMode.externalApplication);
                Navigator.pop(context);
              },
              child: const Text('去更新'),
            ),
          ],
        ),
      );
    }
  }
}

class HomeShell extends StatefulWidget {
  final void Function(BuildContext)? onReady;
  final bool offline;
  const HomeShell({super.key, this.onReady, this.offline = false});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int tab = 0;
  @override
  void initState() {
    super.initState();
    if (!widget.offline) {
      WidgetsBinding.instance.addPostFrameCallback(
          (_) => widget.onReady?.call(context));
    }
  }
  final pages = const [
    BrowsePage(), SearchPage(), QuizPage(), CardsPage(), AiChatPage(),
    TodayPage(),
  ];
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(children: [
        if (widget.offline)
          Container(
            width: double.infinity,
            color: const Color(0xFFF59E0B),
            padding: EdgeInsets.only(
                top: MediaQuery.of(context).padding.top + 4, bottom: 4),
            child: const Text('📴 离线模式 · 显示缓存内容，写操作将在联网后生效',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white, fontSize: 12)),
          ),
        Expanded(child: IndexedStack(index: tab, children: pages)),
      ]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), label: '目录'),
          NavigationDestination(icon: Icon(Icons.search), label: '搜索'),
          NavigationDestination(icon: Icon(Icons.quiz_outlined), label: '刷题'),
          NavigationDestination(icon: Icon(Icons.style_outlined), label: '背卡'),
          NavigationDestination(icon: Icon(Icons.smart_toy_outlined), label: 'AI陪学'),
          NavigationDestination(icon: Icon(Icons.today_outlined), label: '今日'),
        ],
      ),
    );
  }
}
