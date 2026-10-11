import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../main.dart' show Gate, navKey;
import '../../models.dart' show User;
import '../../nav.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';
import '../notes/note_time.dart';
import 'my_notes_page.dart';
import 'settings_page.dart';

class MePage extends StatefulWidget {
  const MePage({super.key});

  @override
  State<MePage> createState() => _MePageState();
}

class _MePageState extends State<MePage> {
  User? _user;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final User u = await Endpoints.me();
      if (!mounted) return;
      setState(() {
        _user = u;
        _failed = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _failed = true);
    }
  }

  Future<void> _logout() async {
    final bool ok =
        await confirmDialog(context, '退出登录', '确定要退出当前账号吗？', okText: '退出');
    if (!ok) return;
    await Api.logout();
    navKey.currentState?.pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const Gate()),
      (Route<dynamic> _) => false,
    );
  }

  void _push(Widget page) {
    Navigator.of(context)
        .push<void>(MaterialPageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final User? u = _user;
    final String name = u?.username ?? (_failed ? '未获取到用户名' : '加载中…');
    final bool admin = u?.isAdmin ?? Api.admin;
    return Scaffold(
      appBar: AppBar(title: const Text('我的')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            AppCard(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: <Widget>[
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: cs.primary.withOpacity(0.14),
                    child: Text(
                      u != null && u.username.isNotEmpty
                          ? u.username.substring(0, 1).toUpperCase()
                          : '?',
                      style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: cs.primary),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        Text('医学知识库',
                            style: TextStyle(
                                fontSize: 12, color: cs.onSurfaceVariant)),
                      ],
                    ),
                  ),
                  if (admin) const AppBadge('管理员', tone: BadgeTone.primary),
                ],
              ),
            ),
            const SizedBox(height: 12),
            AppCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: <Widget>[
                  _tile(Icons.edit_note_outlined, '我的笔记',
                      () => _push(const MyNotesPage())),
                  _divider(),
                  _tile(Icons.error_outline, '错题本', () => openWrongBook(context)),
                  _divider(),
                  _tile(Icons.assignment_outlined, '成绩记录',
                      () => openExams(context)),
                  _divider(),
                  _tile(Icons.tune_outlined, '学习设置',
                      () => _push(const SettingsPage())),
                ],
              ),
            ),
            const SizedBox(height: 12),
            AppCard(
              padding: EdgeInsets.zero,
              child: _tile(Icons.logout, '退出登录', _logout,
                  color: AppColors.of(context).bad),
            ),
          ],
        ),
      ),
    );
  }

  Widget _divider() => const Divider(height: 1, indent: 16, endIndent: 16);

  Widget _tile(IconData icon, String label, VoidCallback onTap, {Color? color}) {
    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(label, style: TextStyle(color: color)),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
