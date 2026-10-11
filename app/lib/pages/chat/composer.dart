import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../widgets/widgets.dart';
import 'upload.dart';

const List<String> kQuickAsks = <String>[
  '考我一道心衰的题',
  '帮我梳理呼吸系统重点',
  '今天该学什么',
];

class Composer extends StatefulWidget {
  final bool busy;
  final void Function(Outgoing o) onSend;
  const Composer({super.key, required this.busy, required this.onSend});

  @override
  State<Composer> createState() => _ComposerState();
}

class _ComposerState extends State<Composer> {
  final TextEditingController _ctl = TextEditingController();
  Attachment? _attach;
  bool _picking = false;

  @override
  void initState() {
    super.initState();
    _ctl.addListener(_onText);
  }

  @override
  void dispose() {
    _ctl.removeListener(_onText);
    _ctl.dispose();
    super.dispose();
  }

  void _onText() => setState(() {});

  bool get _canSend =>
      !widget.busy &&
      !_picking &&
      (_ctl.text.trim().isNotEmpty || _attach != null);

  void _send() {
    if (!_canSend) return;
    final Outgoing o = Outgoing(_ctl.text.trim(), _attach);
    _ctl.clear();
    setState(() => _attach = null);
    widget.onSend(o);
  }

  void _quick(String t) {
    if (widget.busy) return;
    widget.onSend(Outgoing(t, null));
  }

  Future<void> _pick(Future<Attachment?> Function() fn) async {
    setState(() => _picking = true);
    try {
      final Attachment? a = await fn();
      if (!mounted) return;
      if (a != null) setState(() => _attach = a);
    } on UploadError catch (e) {
      if (mounted) toast(context, e.msg);
    } catch (_) {
      if (mounted) toast(context, '选择失败');
    }
    if (mounted) setState(() => _picking = false);
  }

  Future<void> _menu() async {
    FocusScope.of(context).unfocus();
    final String? c = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (BuildContext ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('拍照'),
              onTap: () => Navigator.pop(ctx, 'camera'),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('从相册选择图片'),
              onTap: () => Navigator.pop(ctx, 'gallery'),
            ),
            ListTile(
              leading: const Icon(Icons.description_outlined),
              title: const Text('选择文件'),
              subtitle: const Text('txt/md/csv/json/docx 等，最大 4MB'),
              onTap: () => Navigator.pop(ctx, 'file'),
            ),
          ],
        ),
      ),
    );
    if (c == null || !mounted) return;
    if (c == 'camera') {
      await _pick(() => pickChatImage(ImageSource.camera));
    } else if (c == 'gallery') {
      await _pick(() => pickChatImage(ImageSource.gallery));
    } else {
      await _pick(pickChatFile);
    }
  }

  Widget _preview() {
    final Attachment a = _attach!;
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          padding: const EdgeInsets.fromLTRB(6, 6, 2, 6),
          decoration: BoxDecoration(
            color: cs.onSurface.withOpacity(0.06),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (a.imageBytes != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: Image.memory(a.imageBytes!,
                      width: 44, height: 44, fit: BoxFit.cover),
                )
              else
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 4),
                  child: Icon(Icons.description_outlined),
                ),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 180),
                child: Text(a.isImage ? '图片' : (a.fileName ?? '文件'),
                    overflow: TextOverflow.ellipsis),
              ),
              IconButton(
                tooltip: '移除',
                icon: const Icon(Icons.close, size: 18),
                onPressed: () => setState(() => _attach = null),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    final bool showChips = _ctl.text.isEmpty && _attach == null;
    return Material(
      color: cs.surface,
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Divider(height: 1, color: cs.outlineVariant),
            if (showChips)
              SizedBox(
                height: 48,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  children: kQuickAsks
                      .map((String t) => Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ActionChip(
                              label: Text(t),
                              onPressed: widget.busy ? null : () => _quick(t),
                            ),
                          ))
                      .toList(),
                ),
              ),
            if (_attach != null) _preview(),
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 6, 8, 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: <Widget>[
                  IconButton(
                    tooltip: '添加图片或文件',
                    icon: const Icon(Icons.add_circle_outline),
                    onPressed: (widget.busy || _picking) ? null : _menu,
                  ),
                  Expanded(
                    child: TextField(
                      controller: _ctl,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.newline,
                      keyboardType: TextInputType.multiline,
                      decoration: const InputDecoration(
                        hintText: '问点什么，或让我出题…',
                        isDense: true,
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  IconButton.filled(
                    tooltip: '发送',
                    onPressed: _canSend ? _send : null,
                    icon: const Icon(Icons.send_rounded, size: 20),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
