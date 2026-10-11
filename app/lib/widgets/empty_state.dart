import 'package:flutter/material.dart';

class EmptyState extends StatelessWidget {
  final String text;
  final IconData icon;
  final Widget? action;
  const EmptyState(this.text,
      {super.key, this.icon = Icons.inbox_outlined, this.action});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 40, color: grey),
            const SizedBox(height: 10),
            Text(text, style: TextStyle(color: grey), textAlign: TextAlign.center),
            if (action != null) ...<Widget>[
              const SizedBox(height: 12),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}
