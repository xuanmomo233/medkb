import 'package:flutter/material.dart';
import '../../api.dart';
import '../../models.dart' show VersionInfo;
import '../../self_update.dart';
import '../../widgets/widgets.dart';

String fmtYmd(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

String fmtBytes(int n) {
  if (n < 1024) return '$n B';
  if (n < 1024 * 1024) return '${(n / 1024).toStringAsFixed(1)} KB';
  return '${(n / 1024 / 1024).toStringAsFixed(1)} MB';
}

class SettingsSection extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const SettingsSection({super.key, required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(title,
              style: Theme.of(context)
                  .textTheme
                  .titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class SliderRow extends StatelessWidget {
  final String label;
  final String valueText;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final ValueChanged<double> onChanged;
  final ValueChanged<double>? onChangeEnd;
  const SliderRow({
    super.key,
    required this.label,
    required this.valueText,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.onChanged,
    this.onChangeEnd,
  });

  @override
  Widget build(BuildContext context) {
    final ColorScheme cs = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(child: Text(label)),
            Text(valueText,
                style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                    color: cs.primary)),
          ],
        ),
        Slider(
          value: value.clamp(min, max).toDouble(),
          min: min,
          max: max,
          divisions: divisions,
          onChanged: onChanged,
          onChangeEnd: onChangeEnd,
        ),
      ],
    );
  }
}

class VersionRow extends StatelessWidget {
  final Future<VersionInfo>? future;
  const VersionRow({super.key, required this.future});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return FutureBuilder<VersionInfo>(
      future: future,
      builder: (BuildContext ctx, AsyncSnapshot<VersionInfo> snap) {
        String tail;
        Widget? badge;
        final VersionInfo? v = snap.data;
        if (snap.hasError) {
          tail = '无法检查更新';
        } else if (v == null) {
          tail = '检查中…';
        } else {
          tail = '最新 build ${v.build}';
          final bool newer = v.build > Api.appBuild;
          badge = newer
              ? TextButton(
                  onPressed: () => SelfUpdate.prompt(ctx, v),
                  child: const Text('有新版本·点更新'))
              : const AppBadge('已是最新', tone: BadgeTone.good);
        }
        return Row(
          children: <Widget>[
            Expanded(
              child: Text('当前 build ${Api.appBuild} · $tail',
                  style: TextStyle(color: grey)),
            ),
            if (badge != null) badge,
          ],
        );
      },
    );
  }
}
