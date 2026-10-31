import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/models.dart';

void main() {
  test('chapter galleries read the independent page index without Citation status', () {
    final chapter = ChapterDetail.fromJson(<String, dynamic>{
      'id': 150, 'title': '核酸', 'subject': '生物化学', 'html': '<ul><li>RNA</li></ul>',
      'meta': <String, dynamic>{}, 'pages': <int>[270, 271],
      'citations': <dynamic>[],
      'textbook_pages': <dynamic>[
        <String, dynamic>{'source_key': 'book', 'title': '教材', 'pages': <int>[72, 73]},
      ],
    });
    expect(chapter.citations, isEmpty);
    expect(chapter.textbookPages.single.pages, <int>[72, 73]);
    expect(chapter.textbookPages.single.sourceKey, 'book');
    expect(chapter.pages, <int>[270, 271]);
  });
}
