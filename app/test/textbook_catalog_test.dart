import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medkb/models.dart';
import 'package:medkb/pages/browse/textbook_catalog_page.dart';

void main() {
  const TextbookSource internal = TextbookSource(
    key: 'rjws-internal-medicine-10',
    title: '内科学（第10版）',
    subject: '内科学',
    publisher: '人民卫生出版社',
    edition: '第十版',
  );

  test('textbook source parses the content catalog contract', () {
    final TextbookSource source = TextbookSource.fromJson(<String, dynamic>{
      'key': internal.key,
      'title': internal.title,
      'subject': internal.subject,
      'publisher': internal.publisher,
      'edition': internal.edition,
    });

    expect(source.key, internal.key);
    expect(source.title, internal.title);
    expect(source.publisher, '人民卫生出版社');
    expect(source.edition, '第十版');
  });

  test('PDF URL and auth header use the protected range endpoint', () {
    expect(
      textbookPdfUri('https://example.test', internal.key).toString(),
      'https://example.test/api/textbooks/${internal.key}.pdf',
    );
    expect(
      textbookPdfUri('https://example.test/', internal.key).toString(),
      'https://example.test/api/textbooks/${internal.key}.pdf',
    );
    expect(textbookPdfHeaders('session-token'), <String, String>{
      'X-Token': 'session-token',
    });
  });

  testWidgets('catalog filters textbooks and opens the selected source',
      (WidgetTester tester) async {
    TextbookSource? opened;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: TextbookCatalogList(
          sources: const <TextbookSource>[
            internal,
            TextbookSource(
              key: 'rjws-pathology-10',
              title: '病理学（第10版）',
              subject: '病理学',
              publisher: '人民卫生出版社',
              edition: '第十版',
            ),
          ],
          filter: '病理',
          onOpen: (TextbookSource source) => opened = source,
        ),
      ),
    ));

    expect(find.text('病理学（第10版）'), findsOneWidget);
    expect(find.text('内科学（第10版）'), findsNothing);
    await tester.tap(find.byKey(const ValueKey<String>('textbook-rjws-pathology-10')));
    expect(opened?.key, 'rjws-pathology-10');
  });
}
