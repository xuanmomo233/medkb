import 'package:flutter/material.dart';
import '../../theme.dart';

String fmtTime(String? iso) {
  if (iso == null || iso.isEmpty) return '—';
  final DateTime? d = DateTime.tryParse(iso);
  if (d == null) return iso;
  final DateTime l = d.toLocal();
  String p(int n) => n.toString().padLeft(2, '0');
  return '${l.month}-${p(l.day)} ${p(l.hour)}:${p(l.minute)}';
}

Color rateColor(BuildContext context, double rate) {
  final AppColors c = AppColors.of(context);
  if (rate >= 80) return c.good;
  if (rate >= 60) return c.warn;
  return c.bad;
}
