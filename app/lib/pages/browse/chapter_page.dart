import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';
import 'page_gallery.dart';
import 'note_sections.dart';

class _ChapterReading {
  final ChapterDetail detail;
  final bool isNote;
  const _ChapterReading(this.detail, this.isNote);
}

class _TextbookGallery {
  final String sourceKey;
  final String title;
  final List<int> pages;
  const _TextbookGallery(this.sourceKey, this.title, this.pages);
}

class ChapterPage extends StatefulWidget {
  final int id;
  const ChapterPage(this.id, {super.key});

  @override
  State<ChapterPage> createState() => _ChapterPageState();
}

class _ChapterPageState extends State<ChapterPage> {
  int _section = 0;
  final GlobalKey _contentKey = GlobalKey();

  @override
  void didUpdateWidget(covariant ChapterPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.id != widget.id) _section = 0;
  }

  Future<_ChapterReading> _load() async {
    ContentTree? tree;
    try {
      tree = await Endpoints.tree();
    } catch (_) {
      // The chapter still reads normally if the table of contents is unavailable.
    }
    final ChapterDetail d = await Endpoints.chapter(widget.id);
    return _ChapterReading(d, tree?.notes.any((ChapterBrief n) => n.id == d.id) ?? false);
  }

  Widget _meta(BuildContext context, Map<String, String> meta) {
    final ThemeData t = Theme.of(context);
    final List<MapEntry<String, String>> items =
        meta.entries.where((MapEntry<String, String> e) => e.value.isNotEmpty).toList();
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: items
              .map((MapEntry<String, String> e) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        SizedBox(
                          width: 72,
                          child: Text(e.key,
                              style: TextStyle(
                                  fontSize: 13,
                                  color: t.colorScheme.onSurfaceVariant)),
                        ),
                        Expanded(
                            child: Text(e.value,
                                style: const TextStyle(fontSize: 13))),
                      ],
                    ),
                  ))
              .toList(),
        ),
      ),
    );
  }

  void _selectSection(int index) {
    setState(() => _section = index);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final BuildContext? target = _contentKey.currentContext;
      if (target != null && mounted) {
        Scrollable.ensureVisible(target, duration: const Duration(milliseconds: 240),
            alignment: 0.08);
      }
    });
  }

  Widget _noteBlock(NoteBlock block) {
    if (block.tableColumns <= 0 || block.tableColumns >= 4) {
      // The shared renderer already scrolls tables of four or more columns.
      return HtmlView(block.html);
    }
    return LayoutBuilder(builder: (BuildContext context, BoxConstraints bounds) {
      final double width = math.max(bounds.maxWidth, block.tableColumns * 148.0);
      return SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SizedBox(width: width, child: HtmlView(block.html)),
      );
    });
  }

  Widget _note(BuildContext context, List<NoteSection> sections) {
    final int current = _section.clamp(0, sections.length - 1).toInt();
    final NoteSection selected = sections[current];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Semantics(
          label: '考点精要小节',
          child: DropdownButton<int>(
            value: current,
            isExpanded: true,
            items: <DropdownMenuItem<int>>[
              for (int i = 0; i < sections.length; i++)
                DropdownMenuItem<int>(
                  value: i,
                  child: Text(sections[i].label, maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ),
            ],
            onChanged: (int? index) {
              if (index != null) _selectSection(index);
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Row(children: <Widget>[
            Text('${current + 1} / ${sections.length}',
                style: Theme.of(context).textTheme.bodySmall),
            const Spacer(),
            TextButton(
              onPressed: current > 0 ? () => _selectSection(current - 1) : null,
              child: const Text('上一节'),
            ),
            TextButton(
              onPressed: current + 1 < sections.length
                  ? () => _selectSection(current + 1) : null,
              child: const Text('下一节'),
            ),
          ]),
        ),
        AppCard(
          key: _contentKey,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              for (int i = 0; i < selected.blocks.length; i++) ...<Widget>[
                if (i > 0) const SizedBox(height: 12),
                _noteBlock(selected.blocks[i]),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _body(BuildContext context, _ChapterReading reading, Future<void> Function() refresh) {
    final ChapterDetail d = reading.detail;
    final Map<String, _TextbookGallery> textbook = <String, _TextbookGallery>{};
    for (final ContentCitation citation in d.citations) {
      final int? first = citation.pageStart;
      final int last = citation.pageEnd ?? first ?? 0;
      if (citation.status != 'verified' || first == null || last < first || last - first > 200) continue;
      final current = textbook.putIfAbsent(
        citation.sourceKey,
        () => _TextbookGallery(citation.sourceKey, citation.title, <int>[]),
      );
      for (int page = first; page <= last; page++) {
        if (!current.pages.contains(page)) current.pages.add(page);
      }
    }
    final List<_TextbookGallery> textbookGalleries = textbook.values.toList();
    for (final _TextbookGallery gallery in textbookGalleries) {
      gallery.pages.sort();
    }
    final List<NoteSection> sections =
        reading.isNote ? splitNoteSections(d.html) : <NoteSection>[];
    return AppRefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: reading.isNote
            ? const EdgeInsets.symmetric(horizontal: 16, vertical: 20)
            : const EdgeInsets.all(16),
        children: <Widget>[
          Text(d.title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: AppBadge(d.subject, tone: BadgeTone.primary),
          ),
          _meta(context, d.meta),
          const SizedBox(height: 12),
          if (sections.isNotEmpty)
            Center(child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: _note(context, sections),
            ))
          else
            AppCard(
              padding: const EdgeInsets.all(16),
              child: HtmlView(d.html),
            ),
          if (d.pages.isNotEmpty) ...<Widget>[
            const SizedBox(height: 20),
            PageGallery(pages: d.pages),
          ],
          for (final _TextbookGallery gallery in textbookGalleries) ...<Widget>[
            const SizedBox(height: 20),
            PageGallery(
              pages: gallery.pages,
              title: '教材原图 · ${gallery.title}',
              sourceKey: gallery.sourceKey,
            ),
          ],
          CitationList(d.citations),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('章节')),
      body: AsyncView<_ChapterReading>(
        loader: _load,
        reloadKey: widget.id,
        builder: (BuildContext c, _ChapterReading reading,
                Future<void> Function() refresh) =>
            _body(c, reading, refresh),
      ),
    );
  }
}
