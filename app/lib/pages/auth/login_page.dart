import 'package:flutter/material.dart';
import '../../api.dart';
import '../../theme.dart';
import '../../widgets/widgets.dart';

enum _AuthMode { login, register }

final RegExp _nameRe = RegExp(r'^[\u4e00-\u9fa5A-Za-z0-9_-]{2,24}$');

class LoginPage extends StatefulWidget {
  final VoidCallback onLogin;
  const LoginPage({super.key, required this.onLogin});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _user = TextEditingController();
  final TextEditingController _pwd = TextEditingController();
  final TextEditingController _invite = TextEditingController();
  _AuthMode _mode = _AuthMode.login;
  bool _submitted = false;
  bool _busy = false;
  bool _showPwd = false;
  String _formError = '';
  String _notice = '';

  @override
  void initState() {
    super.initState();
    final String? msg = Api.pendingAuthMsg;
    if (msg != null && msg.isNotEmpty) {
      _notice = msg;
      Api.pendingAuthMsg = null;
    }
  }

  @override
  void dispose() {
    _user.dispose();
    _pwd.dispose();
    _invite.dispose();
    super.dispose();
  }

  String? get _userErr {
    if (!_submitted) return null;
    return _nameRe.hasMatch(_user.text.trim())
        ? null
        : '用户名为 2-24 位中英文、数字、下划线或短横线';
  }

  String? get _pwdErr {
    if (!_submitted) return null;
    return _pwd.text.length >= 8 ? null : '密码至少 8 位';
  }

  String? get _inviteErr {
    if (!_submitted || _mode != _AuthMode.register) return null;
    return _invite.text.trim().isEmpty ? '请输入邀请码' : null;
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _submitted = true;
      _formError = '';
    });
    if (_userErr != null || _pwdErr != null || _inviteErr != null) return;
    setState(() => _busy = true);
    try {
      final String name = _user.text.trim();
      if (_mode == _AuthMode.login) {
        await Api.login(name, _pwd.text);
      } else {
        await Api.register(name, _pwd.text, _invite.text.trim());
      }
      if (!mounted) return;
      widget.onLogin();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _formError = errText(e);
      });
    }
  }

  Future<void> _configServer() async {
    final TextEditingController c = TextEditingController(text: Api.base);
    String? err;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) {
        return StatefulBuilder(
          builder: (BuildContext ctx2, StateSetter setSt) {
            return AlertDialog(
              title: const Text('服务器地址'),
              content: TextField(
                controller: c,
                keyboardType: TextInputType.url,
                autocorrect: false,
                decoration: InputDecoration(
                  hintText: 'https://example.com',
                  errorText: err,
                ),
              ),
              actions: <Widget>[
                TextButton(
                    onPressed: () => Navigator.pop(ctx2, false),
                    child: const Text('取消')),
                FilledButton(
                  onPressed: () {
                    final String v =
                        c.text.trim().replaceAll(RegExp(r'/+$'), '');
                    final String? e = Api.validateBase(v);
                    if (e != null) {
                      setSt(() => err = e);
                      return;
                    }
                    c.text = v;
                    Navigator.pop(ctx2, true);
                  },
                  child: const Text('保存'),
                ),
              ],
            );
          },
        );
      },
    );
    final String value = c.text;
    c.dispose();
    if (ok != true) return;
    await Api.save(base: value);
    if (!mounted) return;
    toast(context, '服务器地址已更新');
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final ColorScheme cs = theme.colorScheme;
    final bool isLogin = _mode == _AuthMode.login;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: <Color>[
              cs.primary.withOpacity(0.14),
              theme.scaffoldBackgroundColor,
            ],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    GestureDetector(
                      onLongPress: _configServer,
                      child: Center(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(20),
                          child: Image.asset(
                            'assets/branding/pulse-cards.png',
                            width: 72,
                            height: 72,
                            fit: BoxFit.cover,
                            excludeFromSemantics: true,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text('医学知识库',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 6),
                    Text('刷题、背卡、AI 陪学，西综备考一站搞定',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(color: cs.onSurfaceVariant)),
                    const SizedBox(height: 20),
                    AppCard(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Segmented<_AuthMode>(
                            options: const <_AuthMode, String>{
                              _AuthMode.login: '登录',
                              _AuthMode.register: '注册',
                            },
                            value: _mode,
                            onChanged: (_AuthMode m) => setState(() {
                              _mode = m;
                              _submitted = false;
                              _formError = '';
                            }),
                          ),
                          const SizedBox(height: 16),
                          if (_notice.isNotEmpty) ...<Widget>[
                            _banner(_notice, AppColors.of(context).warnSoft,
                                AppColors.of(context).warn),
                            const SizedBox(height: 12),
                          ],
                          TextField(
                            controller: _user,
                            enabled: !_busy,
                            autocorrect: false,
                            textInputAction: TextInputAction.next,
                            onChanged: (_) => setState(() {}),
                            decoration: InputDecoration(
                              labelText: '用户名',
                              hintText: '2-24 位，支持中英文',
                              errorText: _userErr,
                              errorMaxLines: 2,
                            ),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _pwd,
                            enabled: !_busy,
                            obscureText: !_showPwd,
                            textInputAction: isLogin
                                ? TextInputAction.done
                                : TextInputAction.next,
                            onChanged: (_) => setState(() {}),
                            onSubmitted: (_) {
                              if (isLogin && !_busy) _submit();
                            },
                            decoration: InputDecoration(
                              labelText: '密码',
                              hintText: '至少 8 位',
                              errorText: _pwdErr,
                              suffixIcon: IconButton(
                                icon: Icon(_showPwd
                                    ? Icons.visibility_off_outlined
                                    : Icons.visibility_outlined),
                                onPressed: () =>
                                    setState(() => _showPwd = !_showPwd),
                              ),
                            ),
                          ),
                          if (!isLogin) ...<Widget>[
                            const SizedBox(height: 12),
                            TextField(
                              controller: _invite,
                              enabled: !_busy,
                              autocorrect: false,
                              textInputAction: TextInputAction.done,
                              onChanged: (_) => setState(() {}),
                              onSubmitted: (_) {
                                if (!_busy) _submit();
                              },
                              decoration: InputDecoration(
                                labelText: '邀请码',
                                hintText: '向管理员获取',
                                errorText: _inviteErr,
                              ),
                            ),
                          ],
                          if (_formError.isNotEmpty) ...<Widget>[
                            const SizedBox(height: 12),
                            _banner(_formError, AppColors.of(context).badSoft,
                                AppColors.of(context).bad),
                          ],
                          const SizedBox(height: 18),
                          SizedBox(
                            height: 48,
                            child: FilledButton(
                              onPressed: _busy ? null : _submit,
                              child: _busy
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2),
                                    )
                                  : Text(isLogin ? '登录' : '注册并登录'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _banner(String text, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration:
          BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
      child: Text(text, style: TextStyle(color: fg, fontSize: 13)),
    );
  }
}
