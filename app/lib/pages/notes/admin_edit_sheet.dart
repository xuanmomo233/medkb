import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' show AdminQuestion, AdminQuestionPatch;
import '../../widgets/widgets.dart';

Future<bool> showAdminEditSheet(BuildContext context, int questionId) async {
  if (!Api.admin) {
    toast(context, '无权限：仅管理员可编辑题目');
    return false;
  }
  return await showAppSheet<bool>(
    context,
    title: '编辑题目 #$questionId',
    builder: (BuildContext ctx) => _AdminEditBody(questionId: questionId),
  ) ?? false;
}

class _AdminEditBody extends StatefulWidget {
  final int questionId;
  const _AdminEditBody({required this.questionId});

  @override
  State<_AdminEditBody> createState() => _AdminEditBodyState();
}

class _AdminEditBodyState extends State<_AdminEditBody> {
  final TextEditingController _stem = TextEditingController();
  final TextEditingController _system = TextEditingController();
  final TextEditingController _tags = TextEditingController();
  final TextEditingController _analysis = TextEditingController();
  AdminQuestion? _orig;
  Object? _err;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _stem.dispose();
    _system.dispose();
    _tags.dispose();
    _analysis.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final AdminQuestion q = await Endpoints.adminQuestion(widget.questionId);
      if (!mounted) return;
      setState(() {
        _orig = q;
        _err = null;
        _stem.text = q.stem;
        _system.text = q.system;
        _tags.text = q.tags.join(', ');
        _analysis.text = q.analysis;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _err = e);
    }
  }

  List<String> _parseTags(String s) => s
      .split(RegExp(r'[,，]'))
      .map((String t) => t.trim())
      .where((String t) => t.isNotEmpty)
      .toList();

  bool _sameList(List<String> a, List<String> b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  Future<void> _save() async {
    final AdminQuestion? o = _orig;
    if (o == null || _saving) return;
    final String stem = _stem.text;
    final String sys = _system.text.trim();
    final List<String> tags = _parseTags(_tags.text);
    final String ana = _analysis.text;
    final String? pStem = stem != o.stem ? stem : null;
    final String? pSys = sys != o.system ? sys : null;
    final List<String>? pTags = _sameList(tags, o.tags) ? null : tags;
    final String? pAna = ana != o.analysis ? ana : null;
    if (pStem == null && pSys == null && pTags == null && pAna == null) {
      toast(context, '没有修改');
      return;
    }
    setState(() => _saving = true);
    try {
      await Endpoints.adminSaveQuestion(widget.questionId,
          AdminQuestionPatch(stem: pStem, system: pSys, tags: pTags, analysis: pAna));
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
    final double h = MediaQuery.of(context).size.height * 0.7;
    final AdminQuestion? o = _orig;
    if (o == null) {
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
      height: h,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              children: <Widget>[
                TextField(
                  controller: _stem,
                  enabled: !_saving,
                  minLines: 4,
                  maxLines: 10,
                  style: const TextStyle(fontFamily: 'monospace'),
                  decoration: const InputDecoration(
                      labelText: '题干（Markdown 原文）', alignLabelWithHint: true),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _system,
                  enabled: !_saving,
                  decoration: const InputDecoration(labelText: '系统'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _tags,
                  enabled: !_saving,
                  decoration: const InputDecoration(
                      labelText: '标签', helperText: '用逗号分隔'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _analysis,
                  enabled: !_saving,
                  minLines: 8,
                  maxLines: 16,
                  decoration: const InputDecoration(
                      labelText: '解析（Markdown 原文）', alignLabelWithHint: true),
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
