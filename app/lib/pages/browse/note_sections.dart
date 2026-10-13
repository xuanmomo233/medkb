import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html_parser;

/// Split already-rendered server HTML at structural headings, without touching
/// its medical wording. HTML parsing keeps nested markup and Unicode intact.
class NoteBlock {
  final String html;
  final int tableColumns;
  const NoteBlock(this.html, {this.tableColumns = 0});
}

class NoteSection {
  final String title;
  final String? parentTitle;
  final int level;
  final List<NoteBlock> blocks;
  const NoteSection(this.title, this.parentTitle, this.level, this.blocks);

  String get label => parentTitle == null ? title : '$parentTitle / $title';
}

List<NoteSection> splitNoteSections(String html) {
  final dom.DocumentFragment document = html_parser.parseFragment(html);
  final List<NoteSection> sections = <NoteSection>[];
  final List<NoteBlock> blocks = <NoteBlock>[];
  final List<dom.Node> pending = <dom.Node>[];
  String title = '概览';
  String? parentTitle;
  String? currentParent;
  int level = 0;
  int headingNumber = 0;

  dom.Node wrapped(dom.Node node, List<dom.Element> containers) {
    dom.Node copy = node.clone(true);
    for (final dom.Element original in containers.reversed) {
      final dom.Element shell = original.clone(false);
      shell.nodes.add(copy);
      copy = shell;
    }
    return copy;
  }

  String serialize(Iterable<dom.Node> nodes) {
    final dom.DocumentFragment fragment = dom.DocumentFragment();
    fragment.nodes.addAll(nodes);
    return fragment.outerHtml;
  }

  void flushBlock() {
    if (pending.isEmpty) return;
    final String markup = serialize(pending);
    final bool substantive = pending.any((dom.Node node) =>
        node is dom.Element || (node.text?.trim().isNotEmpty ?? false));
    if (substantive) blocks.add(NoteBlock(markup));
    pending.clear();
  }

  void finishSection() {
    flushBlock();
    if (blocks.isNotEmpty) {
      sections.add(NoteSection(title, parentTitle, level, List<NoteBlock>.of(blocks)));
      blocks.clear();
    }
  }

  void visit(dom.Node node, List<dom.Element> containers) {
    if (node is dom.Element) {
      if (node.localName == 'div') {
        for (final dom.Node child in node.nodes) {
          visit(child, <dom.Element>[...containers, node]);
        }
        return;
      }
      if (node.localName == 'h2' || node.localName == 'h3') {
        finishSection();
        headingNumber++;
        title = node.text.trim().isEmpty ? '未命名小节 $headingNumber' : node.text.trim();
        level = node.localName == 'h2' ? 2 : 3;
        if (level == 2) currentParent = title;
        parentTitle = level == 3 ? currentParent : null;
        pending.add(wrapped(node, containers));
        return;
      }
      if (node.localName == 'table') {
        flushBlock();
        final dom.Element? row = node.querySelector('tr');
        final int columns = row?.children
                .where((dom.Element cell) => cell.localName == 'td' || cell.localName == 'th')
                .length ??
            0;
        blocks.add(NoteBlock(serialize(<dom.Node>[wrapped(node, containers)]),
            tableColumns: columns));
        return;
      }
    }
    pending.add(wrapped(node, containers));
  }

  for (final dom.Node node in document.nodes) {
    visit(node, <dom.Element>[]);
  }
  finishSection();
  // Headless chapters retain their original uninterrupted HtmlView.
  return headingNumber == 0 ? <NoteSection>[] : sections;
}
