import 'dart:convert';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../api.dart';
import '../widgets.dart';
import 'quiz.dart' show pushQuestionByQid;

/// AI 陪学聊天页：答疑 + 可交互抽背（点选项作答），历史存服务端
class AiChatPage extends StatefulWidget {
  const AiChatPage({super.key});
  @override
  State<AiChatPage> createState() => _AiChatState();
}

class _AiChatState extends State<AiChatPage> {
  final List<Map> msgs = [];   // {role, content, html} 或 {role:'quiz', quiz:{..}}
  final TextEditingController _tc = TextEditingController();
  final ScrollController _sc = ScrollController();
  bool sending = false, loading = true;
  Uint8List? _imgBytes;   // 待发送图片（本地预览用）
  String _imgB64 = '';    // 同图 dataURL，随消息发给服务端
  String _fileName = '', _fileB64 = '';   // 待发送文件（≤4MB 文本类）

  /// 附件菜单：拍照 / 相册图片 / 文件（文本类≤2MB，服务端提取正文）
  Future<void> _pickAttach() async {
    final act = await showModalBottomSheet<String>(
        context: context,
        builder: (ctx) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(leading: const Icon(Icons.photo_camera),
                title: const Text('拍照'),
                onTap: () => Navigator.pop(ctx, 'camera')),
            ListTile(leading: const Icon(Icons.photo_library),
                title: const Text('从相册选择'),
                onTap: () => Navigator.pop(ctx, 'gallery')),
            ListTile(leading: const Icon(Icons.attach_file),
                title: const Text('发文件（txt/md/docx）'),
                onTap: () => Navigator.pop(ctx, 'file')),
          ])));
    if (act == null) return;
    if (act == 'file') { await _pickFile(); return; }
    try {
      final x = await ImagePicker().pickImage(
          source: act == 'camera' ? ImageSource.camera : ImageSource.gallery,
          maxWidth: 1400, maxHeight: 1400, imageQuality: 82);
      if (x == null) return;
      final bytes = await x.readAsBytes();
      if (bytes.lengthInBytes > 4 * 1024 * 1024) {
        if (mounted) toast(context, '图片太大了');
        return;
      }
      setState(() {
        _imgBytes = bytes;
        _imgB64 = 'data:image/jpeg;base64,' + base64Encode(bytes);
      });
    } catch (e) {
      if (mounted) toast(context, '选图失败：$e');
    }
  }

  /// 选文件：仅文本可解析类型，≤4MB（base64 传输）
  Future<void> _pickFile() async {
    try {
      final r = await FilePicker.platform.pickFiles(withData: true,
          type: FileType.custom,
          allowedExtensions: ['txt','md','csv','tsv','json','log','yaml','yml',
              'xml','ini','conf','py','java','sql','htm','html','docx']);
      final f = (r?.files.isNotEmpty == true) ? r!.files.first : null;
      if (f == null || !mounted) return;
      final bytes = f.bytes;
      if (bytes == null) { toast(context, '读不到文件内容'); return; }
      if (bytes.lengthInBytes > 4 * 1024 * 1024) {
        toast(context, '文件超过 4MB 上限，PDF/扫描件截图发我'); return;
      }
      setState(() {
        _fileName = f.name;
        _fileB64 = base64Encode(bytes);
      });
    } catch (e) {
      if (mounted) toast(context, '选文件失败：$e');
    }
  }

  @override
  void initState() {
    super.initState();
    _loadHist();
  }

  @override
  void dispose() { _tc.dispose(); _sc.dispose(); super.dispose(); }

  bool _histErr = false;
  Future<void> _loadHist() async {
    try {
      final j = await Api.get('/api/chat_hist', cache: false);
      msgs.addAll((j as List).cast<Map>());
      _histErr = false;
    } catch (_) { _histErr = true; }
    if (mounted) {
      setState(() => loading = false);
      _toEnd();
    }
  }

  void _toEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_sc.hasClients) _sc.jumpTo(_sc.position.maxScrollExtent);
    });
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _tc.text).trim();
    if ((text.isEmpty && _imgB64.isEmpty && _fileB64.isEmpty) || sending) return;
    _tc.clear();
    final img = _imgB64, bytes = _imgBytes;
    final fname = _fileName, fb64 = _fileB64;
    setState(() {
      _imgBytes = null; _imgB64 = ''; _fileName = ''; _fileB64 = '';
      msgs.add({'role': 'user',
          'content': (text.isEmpty && img.isEmpty && fname.isEmpty)
              ? '（附件）'
              : text + (fname.isNotEmpty ? ' 📎$fname' : '') +
                (img.isNotEmpty ? '（图片）' : ''),
          'html': '', 'img': bytes});
      sending = true;
    });
    _toEnd();
    try {
      final j = await Api.post('/api/chat',
          {'msg': text, 'ctx': viewCtx.value,
           if (img.isNotEmpty) 'img': img,
           if (fb64.isNotEmpty) 'file': {'name': fname, 'data': fb64}},
          secs: 180);
      setState(() {
        msgs.add({'role': 'assistant',
            'content': j['reply'] ?? '', 'html': j['reply_html'] ?? ''});
        final qs = (j['quizzes'] as List?) ??
            (j['quiz'] != null ? [j['quiz']] : const []);
        for (final q in qs) {
          msgs.add({'role': 'quiz', 'quiz': q});
        }
      });
    } catch (e) {
      setState(() => msgs.add({'role': 'assistant',
          'content': '（发送失败：$e）', 'html': '', 'fail': true}));
      _lateSync();   // 服务端可能仍在生成，稍后从历史把回复捞回来
    }
    setState(() => sending = false);
    _toEnd();
  }

  /// 超时/失败后补偿：服务端可能随后才完成并入库，轮询历史把回复补上
  bool _syncing = false;
  Future<void> _lateSync() async {
    if (_syncing) return;
    _syncing = true;
    for (var i = 0; i < 3; i++) {
      await Future.delayed(Duration(seconds: i == 0 ? 20 : 30));
      if (!mounted) break;
      try {
        final j = await Api.get('/api/chat_hist', cache: false);
        final remote = (j as List).cast<Map>();
        final localN = msgs.where((m) => m['role'] != 'quiz').length;
        if (remote.length > localN) {
          final extra = remote.sublist(localN);
          setState(() {
            msgs.removeWhere((m) => m['fail'] == true);
            msgs.addAll(extra);
          });
          _toEnd();
          break;
        }
      } catch (_) {}
    }
    _syncing = false;
  }

  /// 抽背作答回调：判题接口 → 解析气泡，返回判题结果给卡片着色
  Future<Map?> _onAnswer(Map quiz, String ans) async {
    setState(() => sending = true);
    _toEnd();
    Map? res;
    try {
      res = (await Api.post('/api/chat_answer',
          {'qid': quiz['qid'], 'ans': ans}, secs: 150)) as Map;
      setState(() {
        msgs.add({'role': 'assistant',
            'content': res?['reply'] ?? '', 'html': res?['reply_html'] ?? '',
            'qid': quiz['qid']});
      });
    } catch (e) {
      setState(() => msgs.add({'role': 'assistant',
          'content': '（判题失败：$e）', 'html': ''}));
    }
    setState(() => sending = false);
    _toEnd();
    return res;
  }

  Future<void> _clear() async {
    final ok = await showDialog<bool>(context: context, builder: (ctx) =>
      AlertDialog(title: const Text('清空聊天记录？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('清空')),
        ]));
    if (ok == true) {
      try {
        await Api.post('/api/chat_clear', {});
      } catch (_) {
        if (mounted) { toast(context, '清空失败，请检查网络'); return; }
      }
      setState(() => msgs.clear());
    }
  }

  Widget _bubble(Map m, ColorScheme cs) {
    final me = m['role'] == 'user';
    final withQid = m['qid'] != null && m['qid'].toString().isNotEmpty;
    return Align(
      alignment: me ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.86),
        decoration: BoxDecoration(
          color: me ? cs.primaryContainer : cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: me
              ? Column(crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (m['img'] != null)
                      Padding(padding: const EdgeInsets.only(bottom: 4),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.memory(m['img'] as Uint8List,
                              height: 140, fit: BoxFit.cover))),
                    ValueListenableBuilder<double>(
                        valueListenable: fontScale,
                        builder: (_, fs, __) => Text(m['content'] ?? '',
                            style: TextStyle(fontSize: fs, height: 1.7))),
                  ])
              : Column(crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    HtmlView((m['html'] ?? '').toString().isNotEmpty
                        ? m['html'] : (m['content'] ?? '')),
                    if (withQid)
                      Padding(padding: const EdgeInsets.only(top: 4),
                        child: ActionChip(
                          avatar: const Icon(Icons.open_in_new, size: 14),
                          label: Text('查看原题 #${m['qid']}',
                              style: const TextStyle(fontSize: 12)),
                          onPressed: () => pushQuestionByQid(
                              context, m['qid'].toString()))),
                  ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('AI 陪学'),
        actions: [
          IconButton(icon: const Icon(Icons.format_size),
              tooltip: '字号', onPressed: () => showFontSheet(context)),
          IconButton(icon: const Icon(Icons.delete_outline),
              tooltip: '清空记录', onPressed: _clear),
        ]),
      body: Column(children: [
        Expanded(child: loading
            ? const Center(child: CircularProgressIndicator())
            : _histErr && msgs.isEmpty
                ? LoadError(msg: '聊天记录加载失败', onRetry: () {
                    setState(() => loading = true); _loadHist(); })
            : ListView.builder(
                controller: _sc,
                itemCount: msgs.length + (sending ? 1 : 0),
                itemBuilder: (ctx, i) {
                  if (i >= msgs.length) {
                    return Align(alignment: Alignment.centerLeft,
                      child: Container(
                        margin: const EdgeInsets.all(10),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                            color: cs.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(12)),
                        child: const SizedBox(width: 40, height: 14,
                            child: LinearProgressIndicator())));
                  }
                  final m = msgs[i];
                  if (m['role'] == 'quiz') {
                    return QuizCard(quiz: m['quiz'], onAnswer: _onAnswer);
                  }
                  return _bubble(m, cs);
                })),
        if (msgs.isEmpty && !loading)
          Padding(padding: const EdgeInsets.only(bottom: 8),
            child: Wrap(spacing: 8, children: [
              for (final s in ['考我一道生理题', '什么是氧解离曲线？',
                               '抽背：肾小球滤过', '讲讲心衰的治疗原则'])
                ActionChip(label: Text(s, style: const TextStyle(fontSize: 12)),
                    onPressed: () => _send(s)),
            ])),
        if (_imgBytes != null || _fileName.isNotEmpty)
          Align(alignment: Alignment.centerLeft,
            child: Padding(padding: const EdgeInsets.fromLTRB(10, 0, 10, 4),
              child: Wrap(spacing: 8, children: [
                if (_imgBytes != null)
                  Stack(children: [
                    ClipRRect(borderRadius: BorderRadius.circular(8),
                      child: Image.memory(_imgBytes!, height: 64,
                          fit: BoxFit.cover)),
                    Positioned(right: 0, top: 0,
                      child: Semantics(
                        button: true,
                        label: '移除已选图片',
                        onTap: () => setState(
                            () { _imgBytes = null; _imgB64 = ''; }),
                        child: GestureDetector(
                        onTap: () => setState(
                            () { _imgBytes = null; _imgB64 = ''; }),
                        child: Container(
                          decoration: const BoxDecoration(
                              color: Colors.black54, shape: BoxShape.circle),
                          child: const Icon(Icons.close,
                              size: 16, color: Colors.white))))),
                  ]),
                if (_fileName.isNotEmpty)
                  Chip(avatar: const Icon(Icons.attach_file, size: 16),
                    label: Text(_fileName,
                        style: const TextStyle(fontSize: 12),
                        overflow: TextOverflow.ellipsis),
                    onDeleted: () => setState(
                        () { _fileName = ''; _fileB64 = ''; })),
              ]))),
        SafeArea(child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 4, 10, 8),
          child: Row(children: [
            IconButton(icon: const Icon(Icons.add_photo_alternate_outlined),
                tooltip: '发图/文件', onPressed: sending ? null : _pickAttach),
            Expanded(child: TextField(
              controller: _tc, minLines: 1, maxLines: 4,
              decoration: const InputDecoration(
                hintText: '提问/发图，或说「考我 XX」让我抽背你',
                border: OutlineInputBorder(), isDense: true),
              onSubmitted: (_) => _send())),
            const SizedBox(width: 8),
            IconButton.filled(icon: const Icon(Icons.send),
                onPressed: sending ? null : _send),
          ]))),
      ]),
    );
  }
}

/// 可交互抽背卡片：点选项作答，判分后显示对错+「查看原题」
class QuizCard extends StatefulWidget {
  final Map quiz;
  final Future<Map?> Function(Map quiz, String ans) onAnswer;
  const QuizCard({super.key, required this.quiz, required this.onAnswer});
  @override
  State<QuizCard> createState() => _QuizCardState();
}

class _QuizCardState extends State<QuizCard> {
  final Set<String> picked = {};
  bool submitted = false, waiting = false;
  String answer = '';      // 服务端判题后回填的正确答案字母
  bool correct = false;

  ColorScheme get cs => Theme.of(context).colorScheme;

  Future<void> _submit(String single) async {
    if (submitted || waiting) return;
    final multi = widget.quiz['multi'] == true;
    String ans;
    if (multi) {
      if (picked.isEmpty) { toast(context, '先选择选项'); return; }
      ans = (picked.toList()..sort()).join('');
    } else {
      ans = single;
      setState(() => picked.add(single));
    }
    setState(() { submitted = true; waiting = true; });
    final res = await widget.onAnswer(widget.quiz, ans);
    if (mounted) setState(() {
      waiting = false;
      if (res == null) {
        // 判题失败：解锁卡片允许重试，不把选项永久锁死
        submitted = false;
        toast(context, '判题失败，请检查网络后重试');
      } else {
        answer = (res['answer'] ?? '').toString();
        correct = res['correct'] == true;
      }
    });
  }

  /// 选项着色：判题后 对=绿 我选错=红
  Color? _optColor(String k) {
    if (!submitted || waiting || answer.isEmpty) return null;
    if (answer.contains(k)) return Colors.green;
    if (picked.contains(k) && !correct) return Colors.red;
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.quiz;
    final multi = q['multi'] == true;
    final opts = (q['options'] as List?) ?? [];
    return Align(alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.9),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: cs.outlineVariant)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 头部：题型 + 跳原题
              Row(children: [
                Icon(Icons.quiz_outlined, size: 15, color: cs.primary),
                const SizedBox(width: 4),
                Expanded(child: Text(
                  '${q['system'] ?? ''} · ${multi ? '多选' : '单选'}',
                  style: TextStyle(fontSize: 11.5, color: cs.primary))),
                if (!'${q['qid']}'.startsWith('L'))
                  InkWell(
                    onTap: () => pushQuestionByQid(context, '${q['qid']}'),
                    child: Padding(padding: const EdgeInsets.all(2),
                      child: Row(children: [
                        Icon(Icons.open_in_new, size: 13, color: cs.primary),
                        Text(' 原题 #${q['qid']}',
                            style: TextStyle(fontSize: 11, color: cs.primary)),
                      ]))),
              ]),
              const SizedBox(height: 8),
              // 题干（服务端已渲染 html，图片可显示）
              HtmlView(q['stem'] ?? ''),
              const SizedBox(height: 6),
              // 选项列表：可点击
              for (final o in opts)
                _OptTile(
                  letter: o['k'], html: o['html'],
                  picked: picked.contains(o['k']),
                  locked: submitted,
                  multi: multi,
                  resultColor: _optColor(o['k']),
                  onTap: () {
                    if (submitted) return;
                    if (multi) {
                      setState(() => picked.contains(o['k'])
                          ? picked.remove(o['k']) : picked.add(o['k']));
                    } else {
                      _submit(o['k']);
                    }
                  }),
              if (multi && !submitted)
                Align(alignment: Alignment.centerRight,
                  child: Padding(padding: const EdgeInsets.only(top: 6),
                    child: FilledButton(
                      onPressed: waiting ? null : () => _submit(''),
                      child: const Text('提交', style: TextStyle(fontSize: 13))))),
              if (waiting)
                const Padding(padding: EdgeInsets.only(top: 6),
                  child: SizedBox(height: 14,
                      child: LinearProgressIndicator())),
            ]),
        ),
      ));
  }
}

class _OptTile extends StatelessWidget {
  final String letter, html;
  final bool picked, locked, multi;
  final Color? resultColor;
  final VoidCallback onTap;
  const _OptTile({required this.letter, required this.html,
      required this.picked, required this.locked,
      required this.multi, required this.onTap, this.resultColor});
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final sel = picked;
    final rc = resultColor;
    final resTxt = rc == Colors.green ? '，正确答案'
        : rc == Colors.red ? '，你选错了' : '';
    return Semantics(
      button: !locked,
      label: '选项 $letter。${plainHtml(html, 80)}'
          '${sel ? '，已选中' : ''}$resTxt',
      selected: sel,
      checked: multi && sel,
      child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: locked ? null : onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: rc != null ? rc.withOpacity(.14)
                : sel ? cs.primaryContainer.withOpacity(.5) : null,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
                color: rc ?? (sel ? cs.primary : cs.outlineVariant))),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 22, height: 22,
                margin: const EdgeInsets.only(right: 8, top: 1),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: rc ?? (sel ? cs.primary : cs.surface),
                  border: Border.all(
                      color: rc ?? (sel ? cs.primary : cs.outline))),
                alignment: Alignment.center,
                child: Text(letter, style: TextStyle(fontSize: 12,
                    color: (sel || rc != null) ? Colors.white : cs.outline))),
              Expanded(child: ExcludeSemantics(child: HtmlView(html))),
            ]),
        ),
      )));
  }
}
