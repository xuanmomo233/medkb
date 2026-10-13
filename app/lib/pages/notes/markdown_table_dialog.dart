import 'package:flutter/material.dart';
import 'markdown_editing.dart';

/// Dialog owns all cell controllers; its caller owns the editor controller.
Future<String?> showMarkdownTableDialog(BuildContext context) => showDialog<String>(
      context: context,
      builder: (BuildContext context) => const _MarkdownTableDialog(),
    );

class _MarkdownTableDialog extends StatefulWidget {
  const _MarkdownTableDialog();

  @override
  State<_MarkdownTableDialog> createState() => _MarkdownTableDialogState();
}

class _MarkdownTableDialogState extends State<_MarkdownTableDialog> {
  final List<TextEditingController> _headers = <TextEditingController>[
    TextEditingController(text: '列1'),
    TextEditingController(text: '列2'),
  ];
  final List<List<TextEditingController>> _rows = <List<TextEditingController>>[
    <TextEditingController>[TextEditingController(), TextEditingController()],
  ];
  // Removed fields may still be mounted until the next frame. Dispose with the
  // dialog instead of disposing a controller while a TextField still uses it.
  final List<TextEditingController> _retired = <TextEditingController>[];

  @override
  void dispose() {
    for (final TextEditingController controller in <TextEditingController>[
      ..._headers, ..._rows.expand((List<TextEditingController> row) => row),
      ..._retired,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  void _addColumn() {
    if (_headers.length >= 6) return;
    setState(() {
      _headers.add(TextEditingController(text: '列${_headers.length + 1}'));
      for (final List<TextEditingController> row in _rows) {
        row.add(TextEditingController());
      }
    });
  }

  void _removeColumn(int column) {
    if (_headers.length <= 2) return;
    setState(() {
      _retired.add(_headers.removeAt(column));
      for (final List<TextEditingController> row in _rows) {
        _retired.add(row.removeAt(column));
      }
    });
  }

  void _addRow() {
    if (_rows.length >= 12) return;
    setState(() => _rows.add(List<TextEditingController>.generate(
        _headers.length, (int _) => TextEditingController())));
  }

  void _removeRow(int row) {
    if (_rows.length <= 1) return;
    setState(() => _retired.addAll(_rows.removeAt(row)));
  }

  Widget _cell(TextEditingController controller, String label, Key key) => Padding(
        padding: const EdgeInsets.all(4),
        child: SizedBox(
          width: 180,
          child: TextField(
            key: key,
            controller: controller,
            minLines: 1,
            maxLines: 3,
            decoration: InputDecoration(
              labelText: label,
              border: const OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) => Dialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: 800,
            maxHeight: MediaQuery.of(context).size.height * 0.8,
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text('插入 Markdown 表格',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                const Text('2–6 列，1–12 行；竖线与换行将安全转义。宽表可横向滚动。'),
                Wrap(
                  spacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    Text('列 ${_headers.length} / 6 · 行 ${_rows.length} / 12'),
                    TextButton.icon(
                      onPressed: _headers.length < 6 ? _addColumn : null,
                      icon: const Icon(Icons.add),
                      label: const Text('添加列'),
                    ),
                    TextButton.icon(
                      onPressed: _rows.length < 12 ? _addRow : null,
                      icon: const Icon(Icons.add),
                      label: const Text('添加行'),
                    ),
                  ],
                ),
                Flexible(
                  child: SingleChildScrollView(
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Column(
                        children: <Widget>[
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              const SizedBox(width: 48),
                              for (int column = 0; column < _headers.length; column++)
                                Column(
                                  children: <Widget>[
                                    _cell(_headers[column], '表头 ${column + 1}',
                                        ValueKey<String>('table-header-$column')),
                                    IconButton(
                                      tooltip: '删除第 ${column + 1} 列',
                                      onPressed: _headers.length > 2
                                          ? () => _removeColumn(column) : null,
                                      icon: const Icon(Icons.remove_circle_outline),
                                    ),
                                  ],
                                ),
                            ],
                          ),
                          for (int row = 0; row < _rows.length; row++)
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                SizedBox(
                                  width: 48,
                                  child: IconButton(
                                    tooltip: '删除第 ${row + 1} 行',
                                    onPressed: _rows.length > 1
                                        ? () => _removeRow(row) : null,
                                    icon: const Icon(Icons.remove_circle_outline),
                                  ),
                                ),
                                for (int column = 0; column < _headers.length; column++)
                                  _cell(_rows[row][column], '${row + 1}, ${column + 1}',
                                      ValueKey<String>('table-cell-$row-$column')),
                              ],
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  alignment: WrapAlignment.end,
                  spacing: 8,
                  children: <Widget>[
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('取消'),
                    ),
                    FilledButton(
                      onPressed: () => Navigator.of(context).pop(buildMarkdownTable(
                        _headers.map((TextEditingController c) => c.text).toList(),
                        _rows.map((List<TextEditingController> row) =>
                            row.map((TextEditingController c) => c.text).toList()).toList(),
                      )),
                      child: const Text('插入表格'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
}
