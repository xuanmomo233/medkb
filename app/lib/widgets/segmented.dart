import 'package:flutter/material.dart';

/// 分段选择器；options 的迭代顺序即显示顺序（值 -> 文案）
class Segmented<T> extends StatelessWidget {
  final Map<T, String> options;
  final T value;
  final ValueChanged<T> onChanged;
  const Segmented({
    super.key,
    required this.options,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<T>(
      showSelectedIcon: false,
      segments: options.entries
          .map((MapEntry<T, String> e) =>
              ButtonSegment<T>(value: e.key, label: Text(e.value)))
          .toList(),
      selected: <T>{value},
      onSelectionChanged: (Set<T> s) {
        if (s.isNotEmpty) onChanged(s.first);
      },
    );
  }
}
