import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show Invite, UserPrefs, VersionInfo;
import '../../theme.dart';
import '../../widgets/widgets.dart';
import 'settings_parts.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  UserPrefs? _orig;
  Object? _err;
  int _goal = 50;
  String? _examDate;
  int _minSamples = 5;
  double _maxRate = 0.6;
  int _bGoal = 50;
  String? _bDate;
  int _bMin = 5;
  double _bRate = 0.6;
  bool _saving = false;
  bool _saved = false;
  double _font = Api.fontSize;
  int _cacheBytes = 0;
  Future<VersionInfo>? _version;

  @override
  void initState() {
    super.initState();
    _font = Api.fontSize.clamp(13.0, 22.0).toDouble();
    _load();
    _loadCache();
    _version = Endpoints.version();
  }

  static int _clampGoal(int v) => v < 5 ? 5 : (v > 500 ? 500 : v);

  void _apply(UserPrefs p) {
    _orig = p;
    _goal = _clampGoal(p.dailyGoal);
    final String? d = p.examDate;
    _examDate = (d == null || d.isEmpty) ? null : d;
    _minSamples = p.weakMinSamples < 3 ? 3 : (p.weakMinSamples > 50 ? 50 : p.weakMinSamples);
    final double r = p.weakMaxRate < 0.3 ? 0.3 : (p.weakMaxRate > 0.9 ? 0.9 : p.weakMaxRate);
    _maxRate = (r * 20).round() / 20;
    _bGoal = _goal;
    _bDate = _examDate;
    _bMin = _minSamples;
    _bRate = _maxRate;
  }

  Future<void> _load() async {
    try {
      final UserPrefs p = await Endpoints.prefs();
      if (!mounted) return;
      setState(() {
        _err = null;
        _apply(p);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _err = e);
    }
  }

  Future<void> _loadCache() async {
    final int n = await Api.cacheBytes();
    if (!mounted) return;
    setState(() => _cacheBytes = n);
  }

  bool get _dirty =>
      _orig != null &&
      (_goal != _bGoal ||
          _examDate != _bDate ||
          _minSamples != _bMin ||
          (_maxRate - _bRate).abs() > 0.001);

  Future<void> _save() async {
    if (_orig == null) return;
    setState(() {
      _saving = true;
      _saved = false;
    });
    try {
      final UserPrefs p = await Endpoints.savePrefs(
        dailyGoal: _goal,
        examDate: _examDate,
        clearExamDate: _examDate == null && _bDate != null,
        weakMinSamples: _minSamples,
        weakMaxRate: _maxRate,
      );
      if (!mounted) return;
      setState(() {
        _apply(p);
        _saving = false;
        _saved = true;
      });
      toast(context, '已保存');
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      toast(context, errText(e));
    }
  }
  Future<void> _clearCache() async {
    await Api.cacheClear();
    if (!mounted) return;
    toast(context, '缓存已清除');
    _loadCache();
  }

  @override
  Widget build(BuildContext context) {
    Widget body;
    if (_err != null && _orig == null) {
      body = LoadError(
        msg: errText(_err!),
        onRetry: () {
          setState(() => _err = null);
          _load();
        },
      );
    } else if (_orig == null) {
      body = const LoadingView();
    } else {
      body = _content(context);
    }
    return Scaffold(
      appBar: AppBar(title: const Text('学习设置')),
      body: body,
    );
  }

  Widget _content(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool dirty = _dirty;
    final String saveLabel = _saving ? '保存中…' : (!dirty && _saved ? '已保存' : '保存设置');
    final String rateText = '${(_maxRate * 100).round()}%';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: <Widget>[
        SettingsSection(
          title: '学习目标',
          children: <Widget>[
            Row(
              children: <Widget>[
                const Expanded(child: Text('每日目标（题/卡）')),
                IconButton.outlined(
                  onPressed: _goal > 5
                      ? () => setState(() {
                            _goal = _clampGoal(_goal - 5);
                            _saved = false;
                          })
                      : null,
                  icon: const Icon(Icons.remove),
                ),
                SizedBox(
                  width: 64,
                  child: Text('$_goal',
                      textAlign: TextAlign.center,
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w700)),
                ),
                IconButton.outlined(
                  onPressed: _goal < 500
                      ? () => setState(() {
                            _goal = _clampGoal(_goal + 5);
                            _saved = false;
                          })
                      : null,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('考研倒计时'),
              subtitle: Text('${_examDate ?? '未设置'}（由管理员统一设置）',
                  style: TextStyle(color: cs.onSurfaceVariant)),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SettingsSection(
          title: '薄弱点阈值',
          children: <Widget>[
            SliderRow(
              label: '最少样本数',
              valueText: '$_minSamples 题',
              value: _minSamples.toDouble(),
              min: 3,
              max: 50,
              divisions: 47,
              onChanged: (double v) => setState(() {
                _minSamples = v.round();
                _saved = false;
              }),
            ),
            SliderRow(
              label: '正确率上限',
              valueText: rateText,
              value: _maxRate,
              min: 0.3,
              max: 0.9,
              divisions: 12,
              onChanged: (double v) => setState(() {
                _maxRate = (v * 20).round() / 20;
                _saved = false;
              }),
            ),
            Text(
              '某章节至少做过 $_minSamples 题，且正确率低于 $rateText 时，会出现在「薄弱点分析」中。样本越少越敏感，上限越高列出的章节越多。',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant, height: 1.5),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 48,
          child: FilledButton(
            onPressed: (!dirty || _saving) ? null : _save,
            child: Text(saveLabel),
          ),
        ),
        const SizedBox(height: 12),
        SettingsSection(
          title: '阅读字号',
          children: <Widget>[
            SliderRow(
              label: '字号',
              valueText: '${_font.round()}',
              value: _font,
              min: 13,
              max: 22,
              divisions: 9,
              onChanged: (double v) => setState(() => _font = v.roundToDouble()),
              onChangeEnd: (double v) => setFontSize(v.roundToDouble()),
            ),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cs.onSurface.withOpacity(0.05),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text('心肌细胞的动作电位分为 0、1、2、3、4 五个时相。',
                  style: TextStyle(fontSize: _font, height: 1.6)),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SettingsSection(
          title: '缓存与版本',
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text('离线缓存 ${fmtBytes(_cacheBytes)}'),
                ),
                OutlinedButton(
                  onPressed: _cacheBytes > 0 ? _clearCache : null,
                  child: const Text('清除缓存'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            VersionRow(future: _version),
          ],
        ),
        const SizedBox(height: 12),
        const _PasswordSection(),
        if (Api.admin) ...<Widget>[
          const SizedBox(height: 12),
          const _InvitesSection(),
        ],
      ],
    );
  }
}

class _PasswordSection extends StatefulWidget {
  const _PasswordSection();

  @override
  State<_PasswordSection> createState() => _PasswordSectionState();
}

class _PasswordSectionState extends State<_PasswordSection> {
  final TextEditingController _old = TextEditingController();
  final TextEditingController _new1 = TextEditingController();
  final TextEditingController _new2 = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _old.dispose();
    _new1.dispose();
    _new2.dispose();
    super.dispose();
  }

  bool get _ok =>
      _old.text.isNotEmpty &&
      _new1.text.length >= 6 &&
      _new1.text == _new2.text;

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await Endpoints.changePassword(_old.text, _new1.text);
      if (!mounted) return;
      _old.clear();
      _new1.clear();
      _new2.clear();
      toast(context, '密码已修改，其他设备的登录已失效');
      setState(() {});
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
    Widget field(TextEditingController c, String label) => TextField(
          controller: c,
          obscureText: true,
          decoration: InputDecoration(labelText: label, isDense: true),
          onChanged: (_) => setState(() {}),
        );
    return SettingsSection(
      title: '修改密码',
      children: <Widget>[
        field(_old, '原密码'),
        const SizedBox(height: 8),
        field(_new1, '新密码（至少 6 位）'),
        const SizedBox(height: 8),
        field(_new2, '确认新密码'),
        if (_new2.text.isNotEmpty && _new1.text != _new2.text)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('两次输入的新密码不一致',
                style: TextStyle(fontSize: 12, color: cs.error)),
          ),
        const SizedBox(height: 10),
        SizedBox(
          height: 44,
          child: FilledButton(
            onPressed: (!_ok || _busy) ? null : _save,
            child: Text(_busy ? '提交中…' : '修改密码'),
          ),
        ),
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
                subtitle: Text(c.usedBy != null ? '已被 #${c.usedBy} 使用' : '未使用',
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
