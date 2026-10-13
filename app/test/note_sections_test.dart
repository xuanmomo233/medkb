import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/pages/browse/note_sections.dart';

void main() {
  test('headless chapters keep the original continuous renderer', () {
    expect(splitNoteSections('<p>正文</p><table><tr><td>单元格</td></tr></table>'), isEmpty);
  });

  test('outline preserves Unicode, repeated headings and parent hierarchy', () {
    final sections = splitNoteSections(
      '<div><p>前言😀</p><h2>机制</h2><p>甲</p>'
      '<h3>鉴别</h3><p>乙</p><h3>鉴别</h3><p>丙</p></div>',
    );
    expect(sections.map((s) => s.title), ['概览', '机制', '鉴别', '鉴别']);
    expect(sections.map((s) => s.level), [0, 2, 3, 3]);
    expect(sections[2].parentTitle, '机制');
    final combined = sections.expand((s) => s.blocks).map((b) => b.html).join();
    expect(combined, contains('前言😀'));
    expect(RegExp('<h3>').allMatches(combined).length, 2);
    expect(RegExp('<p>甲</p>').allMatches(combined).length, 1);
  });

  test('tables and inline highlights remain intact in their own blocks', () {
    final sections = splitNoteSections(
      '<h2>阅读</h2><p><mark class="manual">重点</mark></p>'
      '<table><tr><th>A</th><th>B</th><th>C</th></tr>'
      '<tr><td>机制</td><td>鉴别</td><td>应用</td></tr></table><p>后文</p>',
    );
    final blocks = sections.single.blocks;
    expect(blocks.length, 3);
    expect(blocks[1].tableColumns, 3);
    expect(blocks[1].html, contains('<table>'));
    expect(blocks[0].html, contains('<mark class="manual">重点</mark>'));
    expect(blocks[2].html, contains('后文'));
  });
}
