import 'package:flutter/material.dart';

/// 加载失败占位：错误文案 + 重试按钮（与空数据明确区分）
class LoadError extends StatelessWidget {
  final String msg;
  final VoidCallback? onRetry;
  const LoadError({super.key, this.msg = '加载失败', this.onRetry});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(Icons.cloud_off_outlined, size: 40, color: grey),
            const SizedBox(height: 10),
            Text(msg, style: TextStyle(color: grey), textAlign: TextAlign.center),
            if (onRetry != null) ...<Widget>[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('重试'),
                onPressed: onRetry,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
