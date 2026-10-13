import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/pages/notes/markdown_editing.dart';

void main() {
  TextEditingValue value(String text, int base, int extent) => TextEditingValue(
    text: text,
    selection: TextSelection(baseOffset: base, extentOffset: extent),
  );

  test('highlight preserves Unicode, reverse selection and outside content', () {
    final TextEditingValue original = value('前😀医学后', 5, 1);
    final TextEditingValue highlighted = highlightMarkdownSelection(original);
    expect(highlighted.text, '前==😀医学==后');
    expect(highlighted.selection.baseOffset, 7);
    expect(highlighted.selection.extentOffset, 3);
    expect(removeMarkdownHighlight(highlighted), original);
    expect(highlightMarkdownSelection(highlighted), highlighted);
    final TextEditingValue nested = value('==医学==', 2, 4);
    expect(highlightMarkdownSelection(nested), nested);
  });

  test('invalid and split-surrogate selections do not modify highlights', () {
    for (final TextEditingValue original in <TextEditingValue>[
      value('😀abc', -1, -1), value('😀abc', 0, 9),
      value('😀abc', 1, 3), value('abc', 1, 1),
    ]) {
      expect(highlightMarkdownSelection(original), original);
    }
    expect(removeMarkdownHighlight(value('==abc==', -1, -1)),
        value('==abc==', -1, -1));
  });

  test('caret, partial inner selections and clipped pairs are safe no-ops', () {
    final TextEditingValue caret = value('x==医学==y', 4, 4);
    expect(removeMarkdownHighlight(caret), caret);
    final TextEditingValue partial = value('x==医学==y', 4, 5);
    expect(removeMarkdownHighlight(partial), partial);
    final TextEditingValue clipped = value('x==医学==y', 0, 4);
    expect(removeMarkdownHighlight(clipped), clipped);
  });

  test('remove multiple full pairs including legacy HTML, keeping unmatched pairs', () {
    final String text = '==甲== / ==乙== <mark>丙</mark> ==未完成';
    final TextEditingValue cleaned = removeMarkdownHighlight(value(text, text.length, 0));
    expect(cleaned.text, '甲 / 乙 丙 ==未完成');
    expect(cleaned.selection.baseOffset, text.length - 21);
    expect(cleaned.selection.extentOffset, 0);
    final TextEditingValue literal = value(r'\==literal==', 3, 8);
    expect(removeMarkdownHighlight(literal), literal);
  });

  test('clipped wrappers cannot merge distinct highlights', () {
    final TextEditingValue clipped = value('==one== and ==two==', 2, 16);
    expect(removeMarkdownHighlight(clipped), clipped);
    final TextEditingValue legacy = value('<mark>abcdef</mark>', 8, 10);
    expect(highlightMarkdownSelection(legacy), legacy);
    expect(highlightMarkdownSelection(value('  ', 0, 2)).text, '  ');
    expect(highlightMarkdownSelection(value(' word ', 0, 6)).text, '== word ==');
  });

  test('table cells escape literal pipes, slash pipes, HTML and all newlines', () {
    expect(escapeMarkdownTableCell('A|B\r\nC\rD\nE'), 'A&#124;B<br>C<br>D<br>E');
    expect(escapeMarkdownTableCell(r'\|<b>&'), r'\\&#124;&lt;b&gt;&amp;');
    final String table = buildMarkdownTable(<String>['标题', 'B|C'],
        <List<String>>[<String>['😀\n医学', '值']]);
    expect(table, '| 标题 | B&#124;C |\n| --- | --- |\n| 😀<br>医学 | 值 |');
    expect(() => buildMarkdownTable(<String>['one'], <List<String>>[<String>['x']]),
        throwsArgumentError);
    expect(() => buildMarkdownTable(<String>['a', 'b'], <List<String>>[]),
        throwsArgumentError);
    expect(() => buildMarkdownTable(<String>['a', 'b'], <List<String>>[<String>['x']]),
        throwsArgumentError);
    final List<String> six = List<String>.filled(6, '列');
    final List<List<String>> twelve = List<List<String>>.generate(
        12, (int _) => List<String>.filled(6, '值'));
    expect(buildMarkdownTable(six, twelve).split('\n').length, 14);
    expect(() => buildMarkdownTable(<String>[...six, '多'], twelve),
        throwsArgumentError);
    expect(() => buildMarkdownTable(six, <List<String>>[...twelve, six]),
        throwsArgumentError);
  });

  test('insert at active cursor without clobbering forward or reverse selection', () {
    const String table = '| A | B |\n| --- | --- |\n| X | Y |';
    for (final List<int> offsets in <List<int>>[<int>[1, 3], <int>[3, 1]]) {
      final TextEditingValue original = value('前😀后', offsets[0], offsets[1]);
      final TextEditingValue result = insertMarkdownTable(original, table);
      final int cursor = offsets[1];
      final String inserted = '\n\n$table\n\n';
      expect(result.text, original.text.substring(0, cursor) + inserted +
          original.text.substring(cursor));
      expect(result.selection.extentOffset, cursor + inserted.length);
    }
    final TextEditingValue invalid = insertMarkdownTable(value('😀', 1, 1), table);
    expect(invalid.text, '😀\n\n$table\n\n');
  });

  test('table insertion reuses blank lines and original CRLF style', () {
    const String source = 'before\r\n\r\nafter';
    final TextEditingValue inserted = insertMarkdownTable(value(source, 10, 10), 'a\nb');
    expect(inserted.text, 'before\r\n\r\na\r\nb\r\n\r\nafter');
    expect(inserted.selection.extentOffset, 18);
    expect(insertMarkdownTable(value('after', -1, -1), 'table').text,
        'after\n\ntable\n\n');
  });
}
