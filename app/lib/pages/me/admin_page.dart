import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import '../../api.dart' show errText;
import '../../endpoints.dart';
import '../../models.dart' show AdminUser, Invite;
import '../../widgets/widgets.dart';
import 'settings_parts.dart';

class AdminPage extends StatelessWidget {
  const AdminPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('管理中心')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const <Widget>[
          _UsersSection(),
          SizedBox(height: 12),
          _InvitesSection(),
        ],
      ),
    );
  }
}

class _UsersSection extends StatefulWidget {
  const _UsersSection();

  @override
  State<_UsersSection> createState() => _UsersSectionState();
}

class _UsersSectionState extends State<_UsersSection> {
  final TextEditingController _nameQ = TextEditingController();
  final TextEditingController _inviteQ = TextEditingController();
  List<AdminUser>? _items;
  bool _busy = false;
  String? _fltName;
  String? _fltInvite;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nameQ.dispose();
    _inviteQ.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final List<AdminUser> list =
          await Endpoints.adminUsers(q: _fltName, invite: _fltInvite);
      if (!mounted) return;
      setState(() => _items = list);
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    }
  }

  String _fmt(String? iso) =>
      (iso == null || iso.isEmpty) ? '—' : iso.substring(0, iso.length < 10 ? iso.length : 10);

  Future<void> _askDelete(AdminUser u) async {
    final bool? go = await showDialog<bool>(
      context: context,
      builder: (BuildContext c) => AlertDialog(
        title: const Text('删除账号'),
        content: Text('将永久删除账号「${u.username}」（#${u.id}）及其全部学习数据，此操作不可恢复。'),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(
                backgroundColor: Theme.of(c).colorScheme.error),
            onPressed: () => Navigator.pop(c, true),
            child: const Text('继续删除'),
          ),
        ],
      ),
    );
    if (go != true || !mounted) return;
    final TextEditingController pw = TextEditingController();
    final String? pass = await showDialog<String>(
      context: context,
      builder: (BuildContext c) => AlertDialog(
        title: const Text('管理员验证'),
        content: TextField(
          controller: pw,
          obscureText: true,
          autofocus: true,
          decoration: const InputDecoration(labelText: '输入管理员账号的密码', isDense: true),
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(
                backgroundColor: Theme.of(c).colorScheme.error),
            onPressed: () => Navigator.pop(c, pw.text),
            child: const Text('确认删除'),
          ),
        ],
      ),
    );
    if (pass == null || pass.isEmpty || !mounted) return;
    setState(() => _busy = true);
    try {
      await Endpoints.adminDeleteUser(u.id, pass);
      if (!mounted) return;
      toast(context, '账号已删除');
      await _load();
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final List<AdminUser> items = _items ?? <AdminUser>[];
    return SettingsSection(
      title: '账户管理',
      children: <Widget>[
        Text('查看全部注册账户；可按用户名搜索，或输入邀请码反查绑定的账号。',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant, height: 1.5)),
        const SizedBox(height: 8),
        TextField(
          controller: _nameQ,
          decoration: const InputDecoration(
              labelText: '按用户名搜索', isDense: true, prefixIcon: Icon(Icons.search)),
          onSubmitted: (_) {
            _fltName = _nameQ.text.trim();
            _fltInvite = null;
            _load();
          },
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _inviteQ,
          decoration: const InputDecoration(
              labelText: '按邀请码反查账号', isDense: true, prefixIcon: Icon(Icons.vpn_key)),
          onSubmitted: (_) {
            _fltInvite = _inviteQ.text.trim();
            _fltName = null;
            _load();
          },
        ),
        if (_fltName != null || _fltInvite != null)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () {
                _nameQ.clear();
                _inviteQ.clear();
                _fltName = null;
                _fltInvite = null;
                _load();
              },
              child: const Text('清除筛选'),
            ),
          ),
        const SizedBox(height: 4),
        if (_items == null)
          const Padding(padding: EdgeInsets.all(12), child: LoadingView())
        else if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('没有匹配的账户'),
          )
        else
          ...items.map((AdminUser u) => ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text('#${u.id} ${u.username}',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                subtitle: Text(
                    '${u.isAdmin ? '管理员 · ' : ''}'
                    '${u.inviteCode != null ? '邀请码 ${u.inviteCode} · ' : ''}'
                    '注册 ${_fmt(u.createdAt)} · 登录 ${_fmt(u.lastLoginAt)}',
                    style: const TextStyle(fontSize: 11)),
                trailing: u.isAdmin
                    ? null
                    : IconButton(
                        tooltip: '删除',
                        icon: Icon(Icons.delete_outline, size: 20, color: cs.error),
                        onPressed: _busy ? null : () => _askDelete(u),
                      ),
              )),
      ],
    );
  }
}

class _InvitesSection extends StatefulWidget {
  const _InvitesSection();

  @override
  State<_InvitesSection> createState() => _InvitesSectionState();
}

class _InvitesSectionState extends State<_InvitesSection> {
  List<Invite>? _items;
  bool _busy = false;
  String _examDate = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final List<Invite> list = await Endpoints.adminInvites();
      final String d = await Endpoints.adminSite();
      if (!mounted) return;
      setState(() {
        _items = list;
        _examDate = d;
      });
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    }
  }

  Future<void> _pickExamDate() async {
    final DateTime now = DateTime.now();
    final DateTime? r = await showDatePicker(
      context: context,
      initialDate: DateTime.tryParse(_examDate) ?? now.add(const Duration(days: 90)),
      firstDate: DateTime(now.year - 1, 1, 1),
      lastDate: DateTime(now.year + 5, 12, 31),
      helpText: '考研日期（全体用户共用）',
    );
    if (r == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final String d = await Endpoints.adminSaveSite(fmtYmd(r));
      if (!mounted) return;
      setState(() => _examDate = d);
      toast(context, '考研日期已更新为 $d');
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _gen(int n) async {
    setState(() => _busy = true);
    try {
      final List<Invite> rows = await Endpoints.adminNewInvites(n);
      if (!mounted) return;
      await Clipboard.setData(ClipboardData(text: rows.first.code));
      toast(context, rows.length > 1 ? '已生成 $n 个邀请码' : '已生成并复制：${rows.first.code}');
      await _load();
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke(Invite c) async {
    try {
      await Endpoints.adminRevokeInvite(c.code);
      if (!mounted) return;
      toast(context, '已撤销');
      await _load();
    } catch (e) {
      if (!mounted) return;
      toast(context, errText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final List<Invite> items = _items ?? <Invite>[];
    return SettingsSection(
      title: '站点管理',
      children: <Widget>[
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          title: const Text('考研日期'),
          subtitle: Text('${_examDate.isEmpty ? '加载中…' : _examDate}（全体用户共用，今日页显示倒计时）',
              style: TextStyle(color: cs.onSurfaceVariant, fontSize: 12)),
          trailing: IconButton(
            tooltip: '修改',
            icon: const Icon(Icons.edit_calendar, size: 20),
            onPressed: _busy ? null : _pickExamDate,
          ),
        ),
        const Divider(height: 16),
        Text('邀请码一次性使用，注册即作废。生成后复制发给新用户。',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant, height: 1.5)),
        const SizedBox(height: 8),
        Row(
          children: <Widget>[
            Expanded(
              child: FilledButton.tonal(
                onPressed: _busy ? null : () => _gen(1),
                child: const Text('生成 1 个'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton(
                onPressed: _busy ? null : () => _gen(5),
                child: const Text('生成 5 个'),
              ),
            ),
          ],
        ),
        if (_items == null)
          const Padding(padding: EdgeInsets.all(12), child: LoadingView())
        else if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('还没有邀请码'),
          )
        else
          ...items.map((Invite c) => ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(c.code,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 13,
                      color: c.usedBy != null ? cs.onSurfaceVariant : cs.primary,
                      decoration: c.usedBy != null ? TextDecoration.lineThrough : null,
                    )),
                subtitle: Text(
                    c.usedBy != null
                        ? '已被 ${c.usedByUsername ?? '#${c.usedBy}'} 使用'
                        : '未使用',
                    style: const TextStyle(fontSize: 12)),
                trailing: c.usedBy == null
                    ? Row(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          IconButton(
                            tooltip: '复制',
                            icon: const Icon(Icons.copy, size: 18),
                            onPressed: () {
                              Clipboard.setData(ClipboardData(text: c.code));
                              toast(context, '已复制');
                            },
                          ),
                          IconButton(
                            tooltip: '撤销',
                            icon: const Icon(Icons.delete_outline, size: 18),
                            onPressed: () => _revoke(c),
                          ),
                        ],
                      )
                    : null,
              )),
      ],
    );
  }
}
