import 'package:flutter/material.dart';
import '../models.dart' show ContentCitation;
import '../theme.dart';

class CitationList extends StatelessWidget {
  final List<ContentCitation> items;
  const CitationList(this.items, {super.key});

  String _location(ContentCitation citation) {
    final List<String> parts = <String>[
      if (citation.chapter.isNotEmpty) citation.chapter,
      if (citation.section.isNotEmpty) citation.section,
    ];
    if (citation.pageStart != null) {
      final int end = citation.pageEnd ?? citation.pageStart!;
      parts.add(end == citation.pageStart
          ? '第 ${citation.pageStart} 页'
          : '第 ${citation.pageStart}-$end 页');
    }
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    final ColorScheme colors = Theme.of(context).colorScheme;
    final AppColors appColors = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: colors.outlineVariant)),
        ),
        child: Padding(
          padding: const EdgeInsets.only(top: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('教材出处', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              for (final ContentCitation citation in items)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Text.rich(TextSpan(children: <InlineSpan>[
                    TextSpan(text: '${citation.publisher}《${citation.title}》${citation.edition}'),
                    if (_location(citation).isNotEmpty) TextSpan(text: ' · ${_location(citation)}'),
                    TextSpan(
                      text: citation.status == 'verified'
                          ? '  已核验'
                          : citation.status == 'disputed' ? '  存在争议' : '  待核验',
                      style: TextStyle(
                        color: citation.status == 'verified'
                            ? appColors.good
                            : citation.status == 'disputed' ? appColors.bad : appColors.warn,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (citation.note.isNotEmpty) TextSpan(text: '\n${citation.note}', style: TextStyle(color: colors.onSurfaceVariant)),
                  ]), style: const TextStyle(fontSize: 12, height: 1.5)),
                ),
            ],
          ),
        ),
      ),
    );
  }

}
