import 'package:flutter/services.dart';

/// Flutter offsets are UTF-16 offsets: never split a surrogate pair.
bool _textBoundary(String text, int offset) {
  if (offset < 0 || offset > text.length) return false;
  if (offset == 0 || offset == text.length) return true;
  final int left = text.codeUnitAt(offset - 1);
  final int right = text.codeUnitAt(offset);
  return !(left >= 0xd800 && left <= 0xdbff &&
      right >= 0xdc00 && right <= 0xdfff);
}

bool hasSafeMarkdownSelection(TextEditingValue value) =>
    value.selection.isValid &&
    _textBoundary(value.text, value.selection.baseOffset) &&
    _textBoundary(value.text, value.selection.extentOffset);

TextSelection _selection(TextSelection source, int base, int extent) =>
    TextSelection(
      baseOffset: base,
      extentOffset: extent,
      affinity: source.affinity,
      isDirectional: source.isDirectional,
    );

/// Keep the selected content selected, including reverse selections.
TextEditingValue highlightMarkdownSelection(TextEditingValue value) {
  if (!hasSafeMarkdownSelection(value) || value.selection.isCollapsed) {
    return value;
  }
  final int start = value.selection.start;
  final int end = value.selection.end;
  final String selected = value.text.substring(start, end);
  // Avoid creating ambiguous or nested delimiters.
  if (selected.trim().isEmpty || selected.contains('==') ||
      RegExp(r'\n[ \t]*\r?\n').hasMatch(selected)) return value;
  for (final span in _highlightSpans(value.text)) {
    if (start < span.end && end > span.start) return value;
  }
  return TextEditingValue(
    text: value.text.replaceRange(start, end, '==$selected=='),
    selection: _selection(value.selection,
        value.selection.baseOffset + 2, value.selection.extentOffset + 2),
  );
}

bool _escaped(String text, int offset) {
  int slashes = 0;
  for (int i = offset - 1; i >= 0 && text[i] == '\\'; i--) {
    slashes++;
  }
  return slashes.isOdd;
}

Iterable<({int start, int end, int open, int close})> _highlightSpans(String text) sync* {
  final RegExp pattern = RegExp(
    r'(?<![=])==((?:(?!==).)+?)==(?![=])|<mark\b[^>]*>([\s\S]*?)</mark\s*>',
    caseSensitive: false, dotAll: true,
  );
  for (final match in pattern.allMatches(text)) {
    final bool markdown = match.group(1) != null;
    if (markdown && (_escaped(text, match.start) || _escaped(text, match.end - 2))) continue;
    final String wrapper = match.group(0)!;
    yield (start: match.start, end: match.end,
        open: markdown ? 2 : wrapper.indexOf('>') + 1,
        close: markdown ? 2 : wrapper.length - wrapper.lastIndexOf('</'));
  }
}

/// Remove only complete pairs or their exact contents, never clipped pairs.
TextEditingValue removeMarkdownHighlight(TextEditingValue value) {
  if (!hasSafeMarkdownSelection(value) || value.selection.isCollapsed) return value;
  final int start = value.selection.start;
  final int end = value.selection.end;
  final List<List<int>> removed = <List<int>>[];
  for (final span in _highlightSpans(value.text)) {
    final bool containsSelection = start == span.start + span.open &&
        end == span.end - span.close;
    final bool fullySelected = start <= span.start && end >= span.end;
    if (containsSelection || fullySelected) {
      removed.add(<int>[span.start, span.start + span.open]);
      removed.add(<int>[span.end - span.close, span.end]);
    } else if (start < span.end && end > span.start) {
      return value;
    }
  }
  if (removed.isEmpty) return value;
  final StringBuffer text = StringBuffer();
  int previous = 0;
  for (final List<int> range in removed) {
    text.write(value.text.substring(previous, range[0]));
    previous = range[1];
  }
  text.write(value.text.substring(previous));
  int mapOffset(int offset) {
    int count = 0;
    for (final List<int> range in removed) {
      if (offset <= range[0]) break;
      count += offset >= range[1] ? range[1] - range[0] : offset - range[0];
    }
    return offset - count;
  }
  return TextEditingValue(
    text: text.toString(),
    selection: _selection(value.selection,
        mapOffset(value.selection.baseOffset), mapOffset(value.selection.extentOffset)),
  );
}

/// Entity pipes remain literal even after a user-entered backslash. Newlines
/// become supported HTML breaks rather than extra Markdown table rows.
String escapeMarkdownTableCell(String value) => value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('\\', '\\\\')
    .replaceAll('|', '&#124;')
    .replaceAll(RegExp(r'\r\n|\r|\n'), '<br>');

String buildMarkdownTable(List<String> headers, List<List<String>> rows) {
  if (headers.length < 2 || headers.length > 6 ||
      rows.isEmpty || rows.length > 12 ||
      rows.any((List<String> row) => row.length != headers.length)) {
    throw ArgumentError('Tables need 2–6 columns and 1–12 equal-width rows.');
  }
  String line(List<String> cells) =>
      '| ${cells.map(escapeMarkdownTableCell).join(' | ')} |';
  return <String>[
    line(headers),
    '| ${List<String>.filled(headers.length, '---').join(' | ')} |',
    ...rows.map(line),
  ].join('\n');
}

/// Insert at the active end of a selection; never replace the selected text.
/// Invalid selections safely append. Preserve every existing character.
TextEditingValue insertMarkdownTable(TextEditingValue value, String table) {
  final int cursor = hasSafeMarkdownSelection(value)
      ? value.selection.extentOffset : value.text.length;
  final String before = value.text.substring(0, cursor);
  final String after = value.text.substring(cursor);
  final String newline = value.text.contains('\r\n') ? '\r\n' : '\n';
  final String normalized = table.replaceAll(RegExp(r'\r\n|\r|\n'), newline);
  final int leading = before.endsWith('$newline$newline') ? 0 :
      before.endsWith(newline) ? 1 : 2;
  final int trailing = after.startsWith('$newline$newline') ? 0 :
      after.startsWith(newline) ? 1 : 2;
  final String inserted = List<String>.filled(leading, newline).join() +
      normalized + List<String>.filled(trailing, newline).join();
  return TextEditingValue(
    text: before + inserted + after,
    selection: TextSelection.collapsed(offset: cursor + inserted.length),
  );
}
