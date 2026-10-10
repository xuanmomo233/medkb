import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';
import 'package:url_launcher/url_launcher.dart';
import 'api.dart';

/// 把正文中的 Q12345 题号变成可点链接（qref:// 协议，由页面接跳题）
/// 不用 lookbehind：部分 Dart/设备正则引擎不支持
final _qrefRe = RegExp(r'(^|[^\w/])Q(\d{4,})');
String linkifyQrefs(String html) => html.replaceAllMapped(_qrefRe,
    (m) => '${m[1]}<a href="qref://${m[2]}">Q${m[2]}</a>');

/// 加载失败占位：错误文案 + 重试按钮（与「空数据」明确区分）
class LoadError extends StatelessWidget {
  final String msg;
  final VoidCallback? onRetry;
  const LoadError({super.key, this.msg = '加载失败', this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.cloud_off_outlined, size: 40, color: Colors.grey),
        const SizedBox(height: 10),
        Text(msg, style: const TextStyle(color: Colors.grey),
            textAlign: TextAlign.center),
        if (onRetry != null) ...[
          const SizedBox(height: 12),
          OutlinedButton.icon(icon: const Icon(Icons.refresh, size: 16),
              label: const Text('重试'), onPressed: onRetry),
        ],
      ])));
  }
}

/// 离线缓存提示条：get() 命中缓存时页面可挂在顶部
class CacheBanner extends StatelessWidget {
  const CacheBanner({super.key});
  @override
  Widget build(BuildContext context) {
    final t = Api.lastCacheTime;
    final age = t == null ? '' : '（${t.month}/${t.day} '
        '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')} 缓存）';
    return Container(
      width: double.infinity,
      color: Colors.grey.withOpacity(0.12),
      padding: const EdgeInsets.symmetric(vertical: 3, horizontal: 12),
      child: Text('📴 离线数据$age', style: const TextStyle(
          fontSize: 11, color: Colors.grey), textAlign: TextAlign.center),
    );
  }
}

/// 全局轻提示（操作反馈必用）
void toast(BuildContext context, String msg) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg), duration: const Duration(seconds: 1),
      behavior: SnackBarBehavior.floating));
}

/// 全局正文字号（默认15，可调 10~20，持久化）
final fontScale = ValueNotifier<double>(Api.fontSize);

/// 用户当前正在浏览的卡片/题目描述，AI 陪学发送消息时带上作为上下文
final viewCtx = ValueNotifier<String>('');

/// 剥掉 HTML 标签取纯文本（给 AI 上下文用）
String plainHtml(String? html, [int max = 400]) {
  var t = (html ?? '')
      .replaceAll(RegExp(r'<img[^>]*>'), '[图]')
      .replaceAll(RegExp(r'!\[[^\]]*\]\([^)]*\)'), '[图]')
      .replaceAll(RegExp(r'<[^>]+>'), ' ');
  t = t.replaceAll(RegExp(r'\s+'), ' ').trim();
  return t.length > max ? t.substring(0, max) : t;
}

/// 字号调节弹层：Aa 按钮调起
void showFontSheet(BuildContext context) {
  showModalBottomSheet(context: context, builder: (_) {
    return StatefulBuilder(builder: (ctx, setS) => Padding(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 30),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Row(children: [
          const Text('Aa', style: TextStyle(fontSize: 13)),
          Expanded(child: Slider(
            value: fontScale.value, min: 10, max: 20, divisions: 20,
            label: fontScale.value.toStringAsFixed(0),
            onChanged: (v) {
              setS(() {});
              fontScale.value = v;
              Api.save(fontSize: v);
            })),
          const Text('Aa', style: TextStyle(fontSize: 20)),
        ]),
        ValueListenableBuilder<double>(
          valueListenable: fontScale,
          builder: (_, v, __) => Text('示例：COPD 的通气功能障碍',
              style: TextStyle(fontSize: v))),
      ]),
    ));
  });
}

/// 目标 URL 是否与 Api.base 同域
bool _sameHost(String url) {
  final u = Uri.tryParse(url);
  final b = Uri.tryParse(Api.base);
  return u != null && b != null &&
      u.host.toLowerCase() == b.host.toLowerCase();
}

/// 外链打开策略：本站域直接开；其他 https 弹确认框；非 https 拦截
Future<bool> _openExternal(BuildContext context, String url) async {
  final u = Uri.tryParse(url);
  if (u == null) return true;
  if (u.scheme != 'https' && u.scheme != 'http') {
    toast(context, '已拦截非网页链接');
    return true;
  }
  if (_sameHost(url)) {
    launchUrl(u, mode: LaunchMode.externalApplication);
    return true;
  }
  if (u.scheme != 'https') {
    toast(context, '已拦截不安全的 http 链接');
    return true;
  }
  final go = await showDialog<bool>(context: context, builder: (_) => AlertDialog(
    title: const Text('打开外部链接？'),
    content: Text('即将离开 App 访问：\n${u.host}\n\n$u',
        style: const TextStyle(fontSize: 13)),
    actions: [
      TextButton(onPressed: () => Navigator.pop(context, false),
          child: const Text('取消')),
      FilledButton(onPressed: () => Navigator.pop(context, true),
          child: const Text('打开')),
    ]));
  if (go == true) {
    launchUrl(u, mode: LaunchMode.externalApplication);
  }
  return true;
}

/// 服务端返回的 HTML（markdown 渲染后）统一显示组件
class HtmlView extends StatelessWidget {
  final String html;
  final void Function(String qid)? onQref;
  const HtmlView(this.html, {super.key, this.onQref});
  @override
  Widget build(BuildContext context) {
    final pri = Theme.of(context).colorScheme.primary;
    final hex = '#${pri.value.toRadixString(16).substring(2)}';
    final body = onQref == null ? html : linkifyQrefs(html);
    return ValueListenableBuilder<double>(
      valueListenable: fontScale,
      builder: (context, fs, _) => HtmlWidget(
      body.isEmpty ? '—' : body,
      baseUrl: Uri.parse(Api.base),
      textStyle: TextStyle(fontSize: fs, height: 1.8),
      onTapUrl: (url) {
        if (url.startsWith('qref://')) {
          onQref?.call(url.substring(7));
          return true;
        }
        return _openExternal(context, url);
      },
      onTapImage: (meta) {
        if (meta.sources.isEmpty) return;
        final raw = meta.sources.first.url;
        // 图片仅放行本站域（相对路径拼 base），站外图片一律拦截
        final url = raw.startsWith('http') ? raw : Api.base + raw;
        if (!_sameHost(url)) {
          toast(context, '已拦截站外图片');
          return;
        }
        showDialog(
          context: context,
          barrierColor: Colors.black.withOpacity(0.92),
          builder: (_) => GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: InteractiveViewer(
              maxScale: 6,
              child: Image.network(url, fit: BoxFit.contain),
            ),
          ),
        );
      },
      customStylesBuilder: (e) {
        // 分节卡片：含子列表的顶层 li
        if (e.localName == 'li' &&
            e.children.any((c) => c.localName == 'ul')) {
          return {
            'background-color': '${hex}0d',
            'border-left': '3px solid $hex',
            'border-radius': '0 10px 10px 0',
            'padding': '8px 12px',
            'margin': '10px 0',
            'list-style-type': 'none',
            'display': 'block',
          };
        }
        switch (e.localName) {
          case 'ul':
            // 嵌套列表缩进线
            if (e.parent?.localName == 'li') {
              return {'border-left': '1px solid ${hex}44',
                      'padding-left': '14px', 'margin': '4px 0'};
            }
            return null;
          case 'strong':
            return {'color': hex, 'font-weight': '700'};
          case 'li':
            return {'margin': '0 0 6px 0'};
          case 'h2':
          case 'h3':
            return {'color': hex};
          case 'mark':
            return {'background-color': '${hex}22', 'color': hex,
                    'font-weight': '700', 'padding': '0 4px',
                    'border-radius': '4px'};
          case 'span':
            final cls = e.classes;
            if (cls.contains('yr')) {
              return {'color': '#888888', 'font-size': '0.85em'};
            }
            if (cls.contains('ex')) return {'color': '#f59e0b'};
            return null;
          case 'blockquote':
            return {'background-color': '${hex}14', 'padding': '10px',
                    'margin': '8px 0', 'border-radius': '0 8px 8px 0',
                    'border-left': '3px solid ${hex}'};
          case 'table':
            return {'font-size': '0.88em'};
          case 'th':
            return {'background-color': '${hex}1f', 'padding': '5px 8px'};
          case 'td':
            return {'padding': '5px 8px'};
        }
        return null;
      },
      ),
    );
  }
}

/// 评分按钮行：😵不认识 😬不熟 😊已掌握 + ⭐
class RateBar extends StatelessWidget {
  final String kind; // 'q' 或 'k'
  final int ref;
  final bool starred;
  final VoidCallback onRated;
  const RateBar({super.key, required this.kind, required this.ref,
      this.starred = false, required this.onRated});
  @override
  Widget build(BuildContext context) {
    Widget btn(String label, Color c, String rating) => Expanded(
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
            foregroundColor: c,
            side: BorderSide(color: c.withOpacity(0.5)),
            padding: const EdgeInsets.symmetric(vertical: 10)),
        onPressed: () async {
          try {
            await mark(kind, ref, rating);
          } catch (_) {
            if (context.mounted) toast(context, '评分记录失败（网络异常），稍后会重记');
          }
          onRated();
        },
        child: Text(label),
      ));
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Row(children: [
        btn('� 不认识', const Color(0xFFDC2626), 'again'),
        const SizedBox(width: 8),
        btn('😬 不熟', const Color(0xFFF59E0B), 'hard'),
        const SizedBox(width: 8),
        btn('😊 已掌握', const Color(0xFF16A34A), 'good'),
      ]),
    );
  }
}

Future<void> mark(String kind, int ref, String rating) =>
    Api.post('/api/mark', {'kind': kind, 'ref': ref, 'rating': rating});
