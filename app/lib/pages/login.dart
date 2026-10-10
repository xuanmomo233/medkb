import 'package:flutter/material.dart';
import '../api.dart';

class LoginPage extends StatefulWidget {
  final VoidCallback onLogin;
  const LoginPage({super.key, required this.onLogin});
  @override
  State<LoginPage> createState() => _LoginState();
}

class _LoginState extends State<LoginPage> {
  final user = TextEditingController();
  final pw = TextEditingController();
  final code = TextEditingController();
  String err = '';
  bool busy = false;
  bool reg = false;
  bool hidePw = true;

  @override
  void initState() {
    super.initState();
    // 401 踢回登录页时的提示（消费一次）
    final m = Api.pendingAuthMsg;
    if (m != null) { err = m; Api.pendingAuthMsg = null; }
  }

  Future<void> _go() async {
    setState(() { busy = true; err = ''; });
    final msg = reg
        ? await Api.register(user.text.trim(), pw.text, code.text.trim())
        : await Api.login(user.text.trim(), pw.text);
    if (msg == null) { widget.onLogin(); return; }
    setState(() { busy = false; err = msg; });
  }

  // 长按 logo 弹出服务器配置（隐藏入口，普通用户用默认地址）
  void _serverDlg() {
    final c = TextEditingController(text: Api.base);
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('服务器地址'),
      content: TextField(controller: c, autofocus: true,
          decoration: const InputDecoration(
              border: OutlineInputBorder(), isDense: true,
              hintText: 'https://...')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx),
            child: const Text('取消')),
        FilledButton(onPressed: () async {
          final v = c.text.trim().replaceAll(RegExp(r'/+$'), '');
          final bad = v.isEmpty ? '地址不能为空' : Api.validateBase(v);
          if (bad != null) {
            ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
                content: Text(bad), behavior: SnackBarBehavior.floating));
            return;
          }
          await Api.save(base: v);
          if (ctx.mounted) Navigator.pop(ctx);
        }, child: const Text('保存')),
      ]));
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Semantics(
                  button: true,
                  label: '应用图标，长按配置服务器地址',
                  onLongPress: _serverDlg,
                  child: GestureDetector(
                  onLongPress: _serverDlg,
                  child: Container(
                    width: 76, height: 76,
                    decoration: BoxDecoration(
                      color: cs.primaryContainer,
                      borderRadius: BorderRadius.circular(22)),
                    child: Icon(Icons.medical_services_outlined,
                        size: 40, color: cs.primary)))),
                const SizedBox(height: 14),
                Text('医学知识库',
                    style: Theme.of(context).textTheme.headlineMedium
                        ?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('刷题 · 错题 · 闪卡 · AI陪学',
                    style: TextStyle(fontSize: 12, color: cs.outline)),
                const SizedBox(height: 26),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('登录')),
                    ButtonSegment(value: true, label: Text('注册')),
                  ],
                  selected: {reg},
                  onSelectionChanged: (s) => setState(() { reg = s.first; err = ''; }),
                  style: const ButtonStyle(
                      visualDensity: VisualDensity.compact),
                ),
                const SizedBox(height: 18),
                TextField(controller: user,
                    decoration: const InputDecoration(
                        labelText: '用户名',
                        prefixIcon: Icon(Icons.person_outline),
                        border: OutlineInputBorder())),
                const SizedBox(height: 12),
                TextField(controller: pw, obscureText: hidePw,
                    decoration: InputDecoration(
                        labelText: '密码',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          icon: Icon(hidePw
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined, size: 20),
                          onPressed: () => setState(() => hidePw = !hidePw)),
                        border: const OutlineInputBorder()),
                    onSubmitted: (_) => _go()),
                if (reg) ...[
                  const SizedBox(height: 12),
                  TextField(controller: code,
                      decoration: const InputDecoration(
                          labelText: '邀请码',
                          prefixIcon: Icon(Icons.key_outlined),
                          border: OutlineInputBorder()),
                      onSubmitted: (_) => _go()),
                ],
                if (err.isNotEmpty)
                  Container(
                    margin: const EdgeInsets.only(top: 14),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 9),
                    decoration: BoxDecoration(
                      color: cs.errorContainer,
                      borderRadius: BorderRadius.circular(10)),
                    child: Row(children: [
                      Icon(Icons.error_outline, size: 16, color: cs.error),
                      const SizedBox(width: 8),
                      Expanded(child: Text(err,
                          style: TextStyle(fontSize: 12.5, color: cs.error))),
                    ])),
                const SizedBox(height: 20),
                SizedBox(width: double.infinity, height: 48,
                  child: FilledButton(
                    onPressed: busy ? null : _go,
                    child: busy
                        ? const SizedBox(height: 20, width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : Text(reg ? '注册并进入' : '登录',
                            style: const TextStyle(fontSize: 15)))),
                const SizedBox(height: 24),
                Text('build ${Api.appBuild}', style: TextStyle(
                    fontSize: 11, color: cs.outline.withOpacity(0.5))),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
