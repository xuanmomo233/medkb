import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show AdminCard, AdminCardPatch;
import '../../widgets/widgets.dart';

Future<bool> showAdminCardEditSheet(BuildContext context, int cardId) async {
  if (!Api.admin) {
    toast(context, '无权限：仅管理员可编辑卡片');
    return false;
  }
  return await showAppSheet<bool>(
        context,
        title: '编辑卡片 #$cardId',
        builder: (BuildContext ctx) => _AdminCardEditBody(cardId: cardId),
      ) ??
      false;
}

class _AdminCardEditBody extends StatefulWidget {
  final int cardId;
  const _AdminCardEditBody({required this.cardId});

  @override
  State<_AdminCardEditBody> createState() => _AdminCardEditBodyState();
}

class _AdminCardEditBodyState extends State<_AdminCardEditBody> {
  final TextEditingController _section = TextEditingController();
  final TextEditingController _term = TextEditingController();
  final TextEditingController _hint = TextEditingController();
  final TextEditingController _body = TextEditingController();
  AdminCard? _orig;
  Object? _err;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _section.dispose();
    _term.dispose();
    _hint.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final AdminCard card = await Endpoints.adminCard(widget.cardId);
      if (!mounted) return;
      setState(() {
        _orig = card;
        _err = null;
        _section.text = card.section;
        _term.text = card.term;
        _hint.text = card.hint;
        _body.text = card.body;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _err = e);
    }
  }

  Future<void> _save() async {
    final AdminCard? orig = _orig;
    if (orig == null || _saving) return;
    final String section = _section.text.trim();
    final String term = _term.text.trim();
    final String hint = _hint.text;
    final String body = _body.text;
    final AdminCardPatch patch = AdminCardPatch(
      section: section == orig.section ? null : section,
      term: term == orig.term ? null : term,
      hint: hint == orig.hint ? null : hint,
      body: body == orig.body ? null : body,
    );
    if (patch.section == null &&
        patch.term == null &&
        patch.hint == null &&
        patch.body == null) {
      toast(context, '没有需要保存的更改');
      return;
    }
    setState(() => _saving = true);
    try {
      await Endpoints.adminSaveCard(widget.cardId, patch);
      if (!mounted) return;
      toast(context, '已保存');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      toast(context, errText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final double height = MediaQuery.of(context).size.height * 0.7;
    if (_orig == null) {
      return SizedBox(
        height: 260,
        child: _err != null
            ? LoadError(
                msg: errText(_err!),
                onRetry: () {
                  setState(() => _err = null);
                  _load();
                },
              )
            : const LoadingView(),
      );
    }
    return SizedBox(
      height: height,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              children: <Widget>[
                TextField(
                  controller: _section,
                  enabled: !_saving,
                  decoration: const InputDecoration(labelText: '分节'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _term,
                  enabled: !_saving,
                  decoration: const InputDecoration(labelText: '标题'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _hint,
                  enabled: !_saving,
                  minLines: 2,
                  maxLines: 5,
                  decoration: const InputDecoration(labelText: '提示'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _body,
                  enabled: !_saving,
                  minLines: 8,
                  maxLines: 16,
                  style: const TextStyle(fontFamily: 'monospace'),
                  decoration: const InputDecoration(
                    labelText: '正文（Markdown 原文）',
                    alignLabelWithHint: true,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
            child: SizedBox(
              height: 48,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(_saving ? '保存中…' : '保存'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
