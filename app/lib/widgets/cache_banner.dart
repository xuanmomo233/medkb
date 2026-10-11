import 'package:flutter/material.dart';
import '../api.dart';

/// 离线数据角标：get() 命中缓存时挂在页面顶部（读 Api.lastCacheTime）
class CacheBanner extends StatelessWidget {
  const CacheBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final DateTime? t = Api.lastCacheTime;
    final String age = t == null
        ? ''
        : '（${t.month}/${t.day} '
            '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')} 缓存）';
    return Container(
      width: double.infinity,
      color: Theme.of(context).colorScheme.onSurface.withOpacity(0.08),
      padding: const EdgeInsets.symmetric(vertical: 3, horizontal: 12),
      child: Text(
        '离线数据$age',
        style: TextStyle(
            fontSize: 11, color: Theme.of(context).colorScheme.onSurfaceVariant),
        textAlign: TextAlign.center,
      ),
    );
  }
}
