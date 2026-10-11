import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';
import 'bubbles.dart';
import 'chat_items.dart';
import 'composer.dart';
import 'quiz_card.dart';
import 'upload.dart';

class _Failed {
  final ChatSendBody body;
  final int userBefore;
  final String msg;
  const _Failed(this.body, this.userBefore, this.msg);
}

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final List<ChatItem> _items = <ChatItem>[];
  final ScrollController _scroll = ScrollController();
  bool _loading = true;
  String? _loadErr;
  bool _pending = false;
  _Failed? _failed;
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  int _nid() => ++_seq;

  ChatItem _text(String role, String text, String html,
      {Uint8List? imageBytes, String? fileName}) {
    return ChatItem(
      id: _nid(),
      kind: ChatItemKind.text,
      role: role,
      text: text,
      html: html,
      imageBytes: imageBytes,
      fileName: fileName,
    );
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadErr = null;
    });
    try {
      final List<ChatMessage> h = await Endpoints.chatHistory();
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(h.map(
              (ChatMessage m) => _text(m.role, m.content, m.html)));
        _loading = false;
      });
      _toBottom(jump: true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadErr = errText(e);
        _loading = false;
      });
    }
  }

  void _toBottom({bool jump = false}) {
    WidgetsBinding.instance.addPostFrameCallback((Duration _) {
      if (!mounted || !_scroll.hasClients) return;
      final double end = _scroll.position.maxScrollExtent;
      if (jump) {
        _scroll.jumpTo(end);
      } else {
        _scroll.animateTo(end,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  void _push(List<ChatItem> list) {
    setState(() => _items.addAll(list));
    _toBottom();
  }

  int _userCount() => _items.where((ChatItem i) => i.isUser).length;

  void _send(Outgoing o) {
    if (_pending) return;
    final Attachment? a = o.attach;
    final String fallback = a == null
        ? o.message
        : (o.message.isNotEmpty
            ? o.message
            : (a.isImage ? '请看这张图片' : '请看这个文件'));
    final String ctx = viewCtx.value;
    final ChatSendBody body = ChatSendBody(
      message: fallback,
      context: ctx.isEmpty ? null : ctx,
      image: a?.imageUrl,
      fileName: a?.fileName,
      fileData: a?.fileData,
    );
    final int before = _userCount();
    _push(<ChatItem>[
      _text('user', o.message, '',
          imageBytes: a?.imageBytes, fileName: a?.fileName),
    ]);
    _request(body, before);
  }

  Future<void> _request(ChatSendBody body, int userBefore) async {
    setState(() {
      _pending = true;
      _failed = null;
    });
    _toBottom();
    try {
      final ChatReply r = await Endpoints.chatSend(body);
      if (!mounted) return;
      _push(<ChatItem>[
        _text('assistant', r.reply, r.replyHtml),
        ...r.quizzes.map((ChatQuiz q) =>
            ChatItem(id: _nid(), kind: ChatItemKind.quiz, quiz: q)),
      ]);
    } catch (e) {
      if (!mounted) return;
      bool found = false;
      if (e is ApiNet && e.msg.contains('Timeout')) {
        found = await _pollLate(userBefore);
        if (!mounted) return;
      }
      if (!found) {
        setState(() => _failed = _Failed(body, userBefore, errText(e)));
        _toBottom();
      }
    }
    if (mounted) setState(() => _pending = false);
  }

  Future<bool> _pollLate(int userBefore) async {
    for (int i = 0; i < 3; i++) {
      await Future<void>.delayed(const Duration(seconds: 6));
      if (!mounted) return false;
      try {
        final List<ChatMessage> h = await Endpoints.chatHistory();
        if (!mounted) return false;
        final int users = h.where((ChatMessage m) => m.role == 'user').length;
        if (h.isNotEmpty && h.last.role == 'assistant' && users > userBefore) {
          _push(<ChatItem>[_text('assistant', h.last.content, h.last.html)]);
          return true;
        }
      } catch (_) {}
    }
    return false;
  }

  Future<void> _clear() async {
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: const Text('清空聊天记录'),
        content: const Text('清空后无法恢复，确定继续吗？'),
        actions: <Widget>[
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('清空')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await Endpoints.chatClear();
      if (!mounted) return;
      setState(() {
        _items.clear();
        _failed = null;
      });
      toast(context, '已清空记录');
    } catch (e) {
      if (mounted) toast(context, errText(e));
    }
  }

  Widget _welcome() {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final Color grey = cs.onSurfaceVariant;
    Widget cap(IconData icon, String t, String d) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: <Widget>[
              Icon(icon, size: 22, color: cs.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Text.rich(TextSpan(children: <InlineSpan>[
                  TextSpan(
                      text: t,
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  TextSpan(text: '  $d', style: TextStyle(color: grey)),
                ])),
              ),
            ],
          ),
        );
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 40, 8, 16),
      child: Column(
        children: <Widget>[
          Icon(Icons.smart_toy_outlined, size: 44, color: cs.primary),
          const SizedBox(height: 12),
          const Text('你好，我是你的 AI 陪学',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('结合你的题库与背卡，陪你高效备考',
              style: TextStyle(color: grey)),
          const SizedBox(height: 20),
          AppCard(
            child: Column(
              children: <Widget>[
                cap(Icons.help_outline, '答疑', '解释知识点、辨析易混概念'),
                cap(Icons.quiz_outlined, '抽背', '随时出题，点选作答并点评'),
                cap(Icons.image_outlined, '看图', '拍照或选图，讲解题目/图表'),
                cap(Icons.description_outlined, '读文件', '上传笔记文档，总结与提问'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _body() {
    if (_loading) return const LoadingView();
    if (_loadErr != null) return LoadError(msg: _loadErr!, onRetry: _load);
    final bool empty = _items.isEmpty && !_pending && _failed == null;
    final List<Widget> children = <Widget>[];
    if (empty) children.add(_welcome());
    for (final ChatItem m in _items) {
      if (m.kind == ChatItemKind.quiz && m.quiz != null) {
        children.add(ChatBubbleRow(
          key: ValueKey<int>(m.id),
          child: QuizCard(
            quiz: m.quiz!,
            onResult: (ChatAnswerResult r) =>
                _push(<ChatItem>[_text('assistant', r.reply, r.replyHtml)]),
          ),
        ));
      } else if (m.isUser) {
        children.add(UserBubble(m, key: ValueKey<int>(m.id)));
      } else {
        children.add(BotBubble(m.html.isNotEmpty ? m.html : m.text,
            key: ValueKey<int>(m.id)));
      }
    }
    if (_pending) children.add(const ThinkingBubble());
    final _Failed? f = _failed;
    if (f != null && !_pending) {
      children.add(ErrorBubble(
          msg: f.msg, onRetry: () => _request(f.body, f.userBefore)));
    }
    return ListView(
      controller: _scroll,
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      children: children,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 陪学'),
        actions: <Widget>[
          ValueListenableBuilder<String>(
            valueListenable: viewCtx,
            builder: (BuildContext c, String v, Widget? _) => v.isEmpty
                ? const SizedBox.shrink()
                : const Padding(
                    padding: EdgeInsets.only(right: 4),
                    child: AppBadge('已带入上下文', tone: BadgeTone.info),
                  ),
          ),
          TextButton(
            onPressed: (_items.isEmpty || _pending) ? null : _clear,
            child: const Text('清空'),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Column(
        children: <Widget>[
          Expanded(child: _body()),
          Composer(busy: _pending, onSend: _send),
        ],
      ),
    );
  }
}
