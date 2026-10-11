import 'package:flutter/material.dart';
import 'api.dart';
import 'self_update.dart';
import 'endpoints.dart';
import 'models.dart' show User, VersionInfo;
import 'pages/auth/login_page.dart';
import 'pages/browse/browse_page.dart';
import 'pages/cards/cards_page.dart';
import 'pages/chat/chat_page.dart';
import 'pages/me/me_page.dart';
import 'pages/quiz/quiz_page.dart';
import 'pages/today/today_page.dart';
import 'theme.dart';

final GlobalKey<NavigatorState> navKey = GlobalKey<NavigatorState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Api.load();
  fontScale.value = Api.fontSize;
  Api.onUnauthorized = () {
    Api.pendingAuthMsg = '登录已过期，请重新登录';
    navKey.currentState?.pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const Gate()),
      (Route<dynamic> _) => false,
    );
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
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
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
  bool? _ok;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    if (Api.token.isEmpty) {
      _ok = false;
      return;
    }
    try {
      final User u = await Endpoints.me();
      await Api.save(admin: u.isAdmin);
      if (mounted) {
        setState(() {
          _ok = true;
          _offline = Api.lastFromCache;
        });
      }
    } on Api401 {
      if (mounted) setState(() => _ok = false);
    } catch (_) {
      // 网络/服务器异常：有 token 则进入离线模式，写操作会真实失败并提示
      if (mounted) {
        setState(() {
          _ok = true;
          _offline = true;
        });
      }
    }
  }

  Future<void> _checkUpdate(BuildContext context) async {
    final VersionInfo? v = await Api.checkUpdate();
    if (v == null || !context.mounted) return;
    await SelfUpdate.prompt(context, v);
  }

  @override
  Widget build(BuildContext context) {
    final bool? ok = _ok;
    if (ok == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!ok) {
      return LoginPage(
        onLogin: () => setState(() {
          _ok = true;
          _offline = false;
        }),
      );
    }
    return HomeShell(offline: _offline, onReady: _checkUpdate);
  }
}

class HomeShell extends StatefulWidget {
  final bool offline;
  final Future<void> Function(BuildContext context)? onReady;
  const HomeShell({super.key, this.offline = false, this.onReady});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;

  static const List<Widget> _pages = <Widget>[
    TodayPage(),
    BrowsePage(),
    QuizPage(),
    CardsPage(),
    ChatPage(),
    MePage(),
  ];

  @override
  void initState() {
    super.initState();
    if (!widget.offline) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) widget.onReady?.call(context);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final Widget stack = IndexedStack(index: _tab, children: _pages);
    return Scaffold(
      body: Column(
        children: <Widget>[
          if (widget.offline)
            Container(
              width: double.infinity,
              color: AppColors.of(context).warn,
              padding: EdgeInsets.only(
                  top: MediaQuery.of(context).padding.top + 4, bottom: 4),
              child: const Text(
                '离线模式 · 显示缓存内容，写操作需联网',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          Expanded(
            child: widget.offline
                ? MediaQuery.removePadding(
                    context: context, removeTop: true, child: stack)
                : stack,
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (int i) => setState(() => _tab = i),
        destinations: const <NavigationDestination>[
          NavigationDestination(icon: Icon(Icons.today_outlined), label: '今日'),
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), label: '目录'),
          NavigationDestination(icon: Icon(Icons.quiz_outlined), label: '刷题'),
          NavigationDestination(icon: Icon(Icons.style_outlined), label: '背卡'),
          NavigationDestination(icon: Icon(Icons.smart_toy_outlined), label: 'AI 陪学'),
          NavigationDestination(icon: Icon(Icons.person_outline), label: '我的'),
        ],
      ),
    );
  }
}
