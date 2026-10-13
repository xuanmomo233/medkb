import 'package:flutter/material.dart';
import '../../api.dart' show errText;
import '../../endpoints.dart';
import '../../widgets/html_view.dart';
import 'markdown_editing.dart';
import 'markdown_table_dialog.dart';

typedef MarkdownPreviewLoader = Future<String> Function(String text, String kind);

/// The edit sheet owns [controller]; this widget owns only its focus/preview state.
class AdminMarkdownEditor extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final String kind;
  final bool enabled;
  final int minLines;
  final int maxLines;
  final MarkdownPreviewLoader? previewLoader;

  const AdminMarkdownEditor({
    super.key,
    required this.controller,
    required this.label,
    required this.kind,
    required this.enabled,
    required this.minLines,
    required this.maxLines,
    this.previewLoader,
  });

  @override
  State<AdminMarkdownEditor> createState() => _AdminMarkdownEditorState();
}

class _AdminMarkdownEditorState extends State<AdminMarkdownEditor> {
  final FocusNode _focus = FocusNode();
  TextEditingValue? _lastSelection;
  String? _previewHtml;
  Object? _previewError;
  bool _previewing = false;
  int _generation = 0;
  late String _sourceText;

  @override
  void initState() {
    super.initState();
    _sourceText = widget.controller.text;
    widget.controller.addListener(_changed);
  }

  @override
  void didUpdateWidget(covariant AdminMarkdownEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_changed);
      _lastSelection = null;
      _sourceText = widget.controller.text;
      _invalidatePreview();
      widget.controller.addListener(_changed);
    }
    if (oldWidget.kind != widget.kind ||
        oldWidget.previewLoader != widget.previewLoader ||
        (oldWidget.enabled && !widget.enabled)) {
      _invalidatePreview();
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    _focus.dispose();
    super.dispose();
  }

  void _invalidatePreview() {
    _generation++;
    _previewHtml = null;
    _previewError = null;
    _previewing = false;
  }

  void _changed() {
    final TextEditingValue current = widget.controller.value;
    if (hasSafeMarkdownSelection(current) && _focus.hasFocus) {
      _lastSelection = current;
    }
    if (current.text == _sourceText) return;
    _sourceText = current.text;
    setState(_invalidatePreview);
  }

  TextEditingValue _toolbarValue() {
    final TextEditingValue current = widget.controller.value;
    final TextEditingValue? previous = _lastSelection;
    if (previous != null && previous.text == current.text &&
        hasSafeMarkdownSelection(previous) &&
        (!hasSafeMarkdownSelection(current) ||
            (!_focus.hasFocus && current.selection.isCollapsed &&
                !previous.selection.isCollapsed))) {
      return current.copyWith(selection: previous.selection);
    }
    return current;
  }

  void _apply(TextEditingValue Function(TextEditingValue) change) {
    if (!widget.enabled) return;
    final TextEditingValue before = _toolbarValue();
    final TextEditingValue after = change(before);
    if (before.text == after.text) return;
    widget.controller.value = after;
    _focus.requestFocus();
  }

  Future<void> _insertTable() async {
    if (!widget.enabled) return;
    final TextEditingValue insertionPoint = _toolbarValue();
    final String? markdown = await showMarkdownTableDialog(context);
    if (!mounted || !widget.enabled || markdown == null) return;
    final TextEditingValue current = _toolbarValue();
    final TextEditingValue target = current.text == insertionPoint.text
        ? current.copyWith(selection: insertionPoint.selection) : current;
    widget.controller.value = insertMarkdownTable(target, markdown);
    _focus.requestFocus();
  }

  Future<void> _preview() async {
    if (!widget.enabled || _previewing) return;
    final String text = widget.controller.text;
    if (text.runes.length > Endpoints.adminPreviewMaxChars) {
      setState(() {
        _previewHtml = null;
        _previewError = '预览最多支持 20,000 个字符，请先缩短正文';
      });
      return;
    }
    final int request = ++_generation;
    setState(() {
      _previewHtml = null;
      _previewError = null;
      _previewing = true;
    });
    try {
      final String html = await (widget.previewLoader?.call(text, widget.kind) ??
          Endpoints.adminPreview(text, kind: widget.kind));
      if (!mounted || request != _generation || !widget.enabled ||
          widget.controller.text != text) return;
      setState(() {
        _previewing = false;
        _previewHtml = html;
      });
    } catch (error) {
      if (!mounted || request != _generation || !widget.enabled ||
          widget.controller.text != text) return;
      setState(() {
        _previewing = false;
        _previewError = error;
      });
    }
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          TextField(
            controller: widget.controller,
            focusNode: _focus,
            enabled: widget.enabled,
            minLines: widget.minLines,
            maxLines: widget.maxLines,
            style: const TextStyle(fontFamily: 'monospace'),
            decoration: InputDecoration(
              labelText: widget.label,
              alignLabelWithHint: true,
              helperText: '选中文字后可用 ==…== 高亮；预览不会保存',
            ),
          ),
          Wrap(
            spacing: 4,
            runSpacing: 0,
            children: <Widget>[
              TextButton.icon(
                onPressed: widget.enabled
                    ? () => _apply(highlightMarkdownSelection) : null,
                icon: const Icon(Icons.highlight_alt),
                label: const Text('高亮选区'),
              ),
              TextButton.icon(
                onPressed: widget.enabled
                    ? () => _apply(removeMarkdownHighlight) : null,
                icon: const Icon(Icons.format_clear),
                label: const Text('移除高亮'),
              ),
              TextButton.icon(
                onPressed: widget.enabled ? _insertTable : null,
                icon: const Icon(Icons.table_chart_outlined),
                label: const Text('插入表格'),
              ),
              TextButton.icon(
                onPressed: widget.enabled && !_previewing ? _preview : null,
                icon: const Icon(Icons.visibility_outlined),
                label: const Text('预览（不保存）'),
              ),
            ],
          ),
          if (_previewing) const LinearProgressIndicator(),
          if (_previewError != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text('预览失败：${_previewError is String ? _previewError : errText(_previewError!)}',
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (_previewHtml != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Text('预览（未保存）',
                      style: Theme.of(context).textTheme.titleSmall),
                  HtmlView(_previewHtml!),
                ],
              ),
            ),
        ],
      );
}
