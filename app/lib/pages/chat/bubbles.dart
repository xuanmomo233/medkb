import 'package:flutter/material.dart';
import '../../widgets/widgets.dart';
import 'chat_items.dart';

class _Row extends StatelessWidget {
  final bool right;
  final Widget child;
  const _Row({required this.right, required this.child});

  @override
  Widget build(BuildContext context) {
    final double maxW = MediaQuery.of(context).size.width * 0.86;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Align(
        alignment: right ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxW),
          child: child,
        ),
      ),
    );
  }
}

BoxDecoration _botDeco(BuildContext context) {
  final ColorScheme cs = Theme.of(context).colorScheme;
  return BoxDecoration(
    color: cs.surface,
    borderRadius: const BorderRadius.only(
      topLeft: Radius.circular(4),
      topRight: Radius.circular(16),
      bottomLeft: Radius.circular(16),
      bottomRight: Radius.circular(16),
    ),
    border: Border.all(color: cs.outlineVariant),
  );
}

class UserBubble extends StatelessWidget {
  final ChatItem item;
  const UserBubble(this.item, {super.key});

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return _Row(
      right: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: cs.primary,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(16),
            topRight: Radius.circular(4),
            bottomLeft: Radius.circular(16),
            bottomRight: Radius.circular(16),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (item.imageBytes != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.memory(item.imageBytes!,
                      width: 180, fit: BoxFit.cover),
                ),
              ),
            if (item.fileName != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(Icons.description_outlined,
                        size: 16, color: cs.onPrimary),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(item.fileName!,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: cs.onPrimary, fontSize: 13)),
                    ),
                  ],
                ),
              ),
            if (item.text.isNotEmpty)
              SelectableText(item.text,
                  style: TextStyle(color: cs.onPrimary, height: 1.5)),
          ],
        ),
      ),
    );
  }
}

class BotBubble extends StatelessWidget {
  final String html;
  const BotBubble(this.html, {super.key});

  @override
  Widget build(BuildContext context) {
    return _Row(
      right: false,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: _botDeco(context),
        child: HtmlView(html),
      ),
    );
  }
}

class ThinkingBubble extends StatelessWidget {
  const ThinkingBubble({super.key});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return _Row(
      right: false,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: _botDeco(context),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 10),
            Text('思考中…', style: TextStyle(color: grey)),
          ],
        ),
      ),
    );
  }
}

class ErrorBubble extends StatelessWidget {
  final String msg;
  final VoidCallback onRetry;
  const ErrorBubble({super.key, required this.msg, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final Color bad = Theme.of(context).colorScheme.error;
    return _Row(
      right: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 10, 8, 6),
        decoration: _botDeco(context).copyWith(
          border: Border.all(color: bad.withOpacity(0.5)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Icon(Icons.error_outline, size: 16, color: bad),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(msg, style: TextStyle(color: bad, height: 1.4)),
                ),
              ],
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('重试'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ChatBubbleRow extends StatelessWidget {
  final Widget child;
  const ChatBubbleRow({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final double maxW = MediaQuery.of(context).size.width * 0.94;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Align(
        alignment: Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxW),
          child: child,
        ),
      ),
    );
  }
}
