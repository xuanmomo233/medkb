import 'package:flutter/material.dart';
import '../../endpoints.dart';
import '../../models.dart' hide Card;
import '../../widgets/widgets.dart';
import 'page_gallery.dart';

class ChapterPage extends StatelessWidget {
  final int id;
  const ChapterPage(this.id, {super.key});

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

  Widget _body(BuildContext context, ChapterDetail d, Future<void> Function() refresh) {
    return AppRefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
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
          AppCard(
            padding: const EdgeInsets.all(16),
            child: HtmlView(d.html),
          ),
          if (d.pages.isNotEmpty) ...<Widget>[
            const SizedBox(height: 20),
            PageGallery(pages: d.pages),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('章节')),
      body: AsyncView<ChapterDetail>(
        loader: () => Endpoints.chapter(id),
        reloadKey: id,
        builder: (BuildContext c, ChapterDetail d,
                Future<void> Function() refresh) =>
            _body(c, d, refresh),
      ),
    );
  }
}
