import 'dart:convert';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';

const int kMaxImageBytes = 6 * 1024 * 1024;
const int kMaxFileBytes = 4 * 1024 * 1024;
const double kMaxImageSide = 1280;

const List<String> kFileExts = <String>[
  'txt',
  'md',
  'csv',
  'tsv',
  'json',
  'log',
  'yaml',
  'yml',
  'xml',
  'ini',
  'conf',
  'py',
  'java',
  'sql',
  'htm',
  'html',
  'docx',
];

class UploadError implements Exception {
  final String msg;
  const UploadError(this.msg);
  @override
  String toString() => msg;
}

/// 待发送附件：图片（dataURL + 预览字节）或文件（文件名 + base64）
class Attachment {
  final Uint8List? imageBytes;
  final String? imageUrl;
  final String? fileName;
  final String? fileData;
  const Attachment({this.imageBytes, this.imageUrl, this.fileName, this.fileData});

  bool get isImage => imageUrl != null;
}

class Outgoing {
  final String message;
  final Attachment? attach;
  const Outgoing(this.message, this.attach);
}

String _imageMime(Uint8List b) {
  if (b.length > 4 && b[0] == 0x89 && b[1] == 0x50) return 'image/png';
  if (b.length > 4 && b[0] == 0x47 && b[1] == 0x49) return 'image/gif';
  if (b.length > 12 && b[8] == 0x57 && b[9] == 0x45) return 'image/webp';
  return 'image/jpeg';
}

/// 取消选择返回 null；失败抛 UploadError
Future<Attachment?> pickChatImage(ImageSource source) async {
  final XFile? x;
  try {
    x = await ImagePicker().pickImage(
      source: source,
      maxWidth: kMaxImageSide,
      maxHeight: kMaxImageSide,
      imageQuality: 82,
    );
  } catch (_) {
    throw const UploadError('无法打开相机/相册，请检查权限');
  }
  if (x == null) return null;
  final Uint8List bytes;
  try {
    bytes = await x.readAsBytes();
  } catch (_) {
    throw const UploadError('图片读取失败');
  }
  if (bytes.length > kMaxImageBytes) throw const UploadError('图片过大（最大 6MB）');
  return Attachment(
    imageBytes: bytes,
    imageUrl: 'data:${_imageMime(bytes)};base64,${base64Encode(bytes)}',
  );
}

Future<Attachment?> pickChatFile() async {
  final FilePickerResult? r;
  try {
    r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: kFileExts,
      withData: true,
    );
  } catch (_) {
    throw const UploadError('无法打开文件选择器');
  }
  if (r == null || r.files.isEmpty) return null;
  final PlatformFile f = r.files.first;
  final Uint8List? bytes = f.bytes;
  if (bytes == null) throw const UploadError('文件读取失败');
  if (bytes.length > kMaxFileBytes) throw const UploadError('文件过大（最大 4MB）');
  return Attachment(fileName: f.name, fileData: base64Encode(bytes));
}
