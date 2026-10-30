import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../../api.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';

Uri textbookPdfUri(String base, String sourceKey) {
  final String normalizedBase = base.replaceFirst(RegExp(r'/+$'), '');
  return Uri.parse(
    '$normalizedBase/api/textbooks/${Uri.encodeComponent(sourceKey)}.pdf',
  );
}

Map<String, String> textbookPdfHeaders(String token) => <String, String>{
      'X-Token': token,
    };

class TextbookCatalogList extends StatelessWidget {
  final List<TextbookSource> sources;
  final String filter;
  final Future<void> Function()? onRefresh;
  final ValueChanged<TextbookSource>? onOpen;

  const TextbookCatalogList({
    super.key,
    required this.sources,
    this.filter = '',
    this.onRefresh,
    this.onOpen,
  });

  @override
  Widget build(BuildContext context) {
    final String keyword = filter.trim().toLowerCase();
    final List<TextbookSource> visible = sources.where((TextbookSource source) {
      if (keyword.isEmpty) return true;
      return '${source.subject} ${source.title} ${source.publisher} ${source.edition}'
          .toLowerCase()
          .contains(keyword);
    }).toList();
    final Map<String, List<TextbookSource>> groups = <String, List<TextbookSource>>{};
    for (final TextbookSource source in visible) {
      groups.putIfAbsent(source.subject, () => <TextbookSource>[]).add(source);
    }
    final Widget content = visible.isEmpty
        ? ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            children: <Widget>[
              const SizedBox(height: 80),
              EmptyState(keyword.isEmpty ? '暂无教材' : '没有匹配的教材'),
            ],
          )
        : ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            children: <Widget>[
              for (final MapEntry<String, List<TextbookSource>> group
                  in groups.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Card(
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: <Widget>[
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                          child: Text(
                            group.key,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.primary,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        for (final TextbookSource source in group.value)
                          ListTile(
                            key: ValueKey<String>('textbook-${source.key}'),
                            leading: const Icon(Icons.menu_book_outlined),
                            title: Text(source.title),
                            subtitle: Text(
                              '${source.publisher} · ${source.edition}',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () {
                              final ValueChanged<TextbookSource>? onOpen = this.onOpen;
                              if (onOpen != null) {
                                onOpen(source);
                              } else {
                                Navigator.of(context).push<void>(
                                  MaterialPageRoute<void>(
                                    builder: (_) => TextbookReaderPage(source: source),
                                  ),
                                );
                              }
                            },
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          );

    if (onRefresh == null) return content;
    return AppRefreshIndicator(onRefresh: onRefresh!, child: content);
  }
}

class TextbookReaderPage extends StatefulWidget {
  final TextbookSource source;
  const TextbookReaderPage({super.key, required this.source});

  @override
  State<TextbookReaderPage> createState() => _TextbookReaderPageState();
}

class _TextbookReaderPageState extends State<TextbookReaderPage> {
  final PdfViewerController _controller = PdfViewerController();
  PdfDocument? _outlineDocument;
  List<PdfOutlineNode> _outline = <PdfOutlineNode>[];
  int _currentPage = 1;
  int _pageCount = 0;

  void _documentChanged(PdfDocument? document) {
    if (document == null || identical(document, _outlineDocument)) return;
    _outlineDocument = document;
    _pageCount = document.pages.length;
    _loadOutline(document);
    if (mounted) setState(() {});
  }

  Future<void> _loadOutline(PdfDocument document) async {
    try {
      final List<PdfOutlineNode> outline = await document.loadOutline();
      if (mounted && identical(document, _outlineDocument)) {
        setState(() => _outline = outline);
      }
    } catch (_) {
      // Some PDFs have no outline or a malformed outline; page controls remain usable.
    }
  }

  void _pageChanged(int? page) {
    final int next = page ?? _controller.pageNumber ?? 1;
    if (!mounted || next == _currentPage) return;
    setState(() => _currentPage = next);
  }

  void _viewerReady(PdfDocument document, PdfViewerController controller) {
    if (!mounted) return;
    setState(() {
      _pageCount = document.pages.length;
      _currentPage = controller.pageNumber ?? 1;
    });
  }

  Future<void> _jumpToPage() async {
    final TextEditingController input =
        TextEditingController(text: '$_currentPage');
    final int? requested = await showDialog<int>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: const Text('跳转页码'),
        content: TextField(
          controller: input,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: '页码',
            helperText: _pageCount > 0 ? '共 $_pageCount 页' : null,
          ),
          onSubmitted: (String value) => Navigator.pop(
            dialogContext,
            int.tryParse(value),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(
              dialogContext,
              int.tryParse(input.text.trim()),
            ),
            child: const Text('跳转'),
          ),
        ],
      ),
    );
    input.dispose();
    if (requested == null || !mounted || !_controller.isReady || _pageCount <= 0) {
      return;
    }
    final int page = requested.clamp(1, _controller.pageCount).toInt();
    await _controller.goToPage(pageNumber: page);
  }

  Future<void> _showBookmarks() async {
    if (_outline.isEmpty) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (BuildContext sheetContext) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(sheetContext).height * 0.72,
          child: Column(
            children: <Widget>[
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 8, 8),
                child: Row(
                  children: <Widget>[
                    const Expanded(
                      child: Text(
                        '教材目录书签',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                      ),
                    ),
                    IconButton(
                      tooltip: '关闭',
                      onPressed: () => Navigator.pop(sheetContext),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  children: _outline.map(_bookmarkTile).toList(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _bookmarkTile(PdfOutlineNode node) {
    final int? page = node.dest?.pageNumber;
    if (node.children.isEmpty) {
      return ListTile(
        title: Text(node.title),
        trailing: page == null ? null : Text('第 $page 页'),
        enabled: page != null,
        onTap: page == null
            ? null
            : () {
                Navigator.pop(context);
                _controller.goToPage(pageNumber: page);
              },
      );
    }
    return ExpansionTile(
      title: Text(node.title),
      children: <Widget>[
        if (page != null)
          ListTile(
            dense: true,
            title: const Text('跳转到本节'),
            trailing: Text('第 $page 页'),
            onTap: () {
              Navigator.pop(context);
              _controller.goToPage(pageNumber: page);
            },
          ),
        for (final PdfOutlineNode child in node.children) _bookmarkTile(child),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final Uri uri = textbookPdfUri(Api.base, widget.source.key);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.source.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: <Widget>[
          IconButton(
            tooltip: '目录书签',
            onPressed: _outline.isEmpty ? null : _showBookmarks,
            icon: const Icon(Icons.list_alt),
          ),
        ],
      ),
      body: PdfViewer.uri(
        uri,
        headers: textbookPdfHeaders(Api.token),
        preferRangeAccess: true,
        controller: _controller,
        params: PdfViewerParams(
          backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
          sizeDelegateProvider: const PdfViewerSizeDelegateProviderLegacy(maxScale: 8),
          zoomStepsDelegateProvider: const PdfViewerZoomStepsDelegateProviderSmart(
            zoomStep: 1.2,
            minZoomStep: 1.1,
          ),
          textSelectionParams: const PdfTextSelectionParams(enabled: true),
          onDocumentChanged: _documentChanged,
          onViewerReady: _viewerReady,
          onPageChanged: _pageChanged,
          loadingBannerBuilder: (BuildContext context, int loaded, int? total) {
            final double? progress = total == null || total <= 0
                ? null
                : (loaded / total).clamp(0, 1).toDouble();
            return Material(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    const Text('正在读取教材原书'),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: 220,
                      child: LinearProgressIndicator(value: progress),
                    ),
                  ],
                ),
              ),
            );
          },
          errorBannerBuilder: (BuildContext context, Object error,
              StackTrace? stackTrace, PdfDocumentRef documentRef) =>
              Material(
            color: Theme.of(context).colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                '教材加载失败，请检查网络或登录状态后重试。',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onErrorContainer,
                ),
              ),
            ),
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Material(
          elevation: 4,
          color: Theme.of(context).colorScheme.surface,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: Row(
              children: <Widget>[
                IconButton(
                  tooltip: '上一页',
                  onPressed: _controller.isReady && _currentPage > 1
                      ? () => _controller.goToPage(pageNumber: _currentPage - 1)
                      : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: TextButton(
                    onPressed: _controller.isReady ? _jumpToPage : null,
                    child: Text(
                      _pageCount > 0 ? '$_currentPage / $_pageCount · 跳转' : '正在读取页码…',
                    ),
                  ),
                ),
                IconButton(
                  tooltip: '缩小',
                  onPressed: _controller.isReady
                      ? () => _controller.zoomDown()
                      : null,
                  icon: const Icon(Icons.remove),
                ),
                IconButton(
                  tooltip: '放大',
                  onPressed: _controller.isReady
                      ? () => _controller.zoomUp()
                      : null,
                  icon: const Icon(Icons.add),
                ),
                IconButton(
                  tooltip: '下一页',
                  onPressed: _controller.isReady && _currentPage < _pageCount
                      ? () => _controller.goToPage(pageNumber: _currentPage + 1)
                      : null,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
