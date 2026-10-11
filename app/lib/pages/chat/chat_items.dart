import 'dart:typed_data';
import '../../models.dart' hide Card;

enum ChatItemKind { text, quiz }

class ChatItem {
  final int id;
  final ChatItemKind kind;
  final String role;
  final String text;
  final String html;
  final Uint8List? imageBytes;
  final String? fileName;
  final ChatQuiz? quiz;

  const ChatItem({
    required this.id,
    required this.kind,
    this.role = 'assistant',
    this.text = '',
    this.html = '',
    this.imageBytes,
    this.fileName,
    this.quiz,
  });

  bool get isUser => kind == ChatItemKind.text && role == 'user';
}
