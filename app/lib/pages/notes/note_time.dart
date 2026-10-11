import 'package:flutter/material.dart';

String fmtNoteTime(String s) {
  if (s.isEmpty) return '';
  final String t = s.replaceFirst('T', ' ');
  return t.length > 16 ? t.substring(0, 16) : t;
}

Future<bool> confirmDialog(BuildContext context, String title, String message,
    {String okText = '确定'}) async {
  final bool? r = await showDialog<bool>(
    context: context,
    builder: (BuildContext ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: <Widget>[
        TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消')),
        FilledButton(
            onPressed: () => Navigator.pop(ctx, true), child: Text(okText)),
      ],
    ),
  );
  return r == true;
}
