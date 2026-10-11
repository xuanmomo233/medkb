import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api.dart';
import '../theme.dart';
import 'toast.dart';

/// 用户当前正在浏览的卡片/题目描述，AI 陪学发送消息时可带上作为上下文
final ValueNotifier<String> viewCtx = ValueNotifier<String>('');

/// 剥掉 HTML 标签取纯文本（给 AI 上下文/摘要用）
String plainHtml(String? html, [int max = 400]) {
  String t = (html ?? '')
      .replaceAll(RegExp(r'<img[^>]*>'), '[图]')
      .replaceAll(RegExp(r'<[^>]+>'), ' ');
  t = t.replaceAll(RegExp(r'\s+'), ' ').trim();
  return t.length > max ? t.substring(0, max) : t;
}

final RegExp _qrefRe = RegExp(r'(^|[^\w/])Q(\d{4,})');

/// 把正文中的 Q12345 题号变成 qref:// 链接
String linkifyQrefs(String html) => html.replaceAllMapped(
    _qrefRe, (Match m) => '${m[1]}<a href="qref://${m[2]}">Q${m[2]}</a>');

bool _sameHost(String url) {
  final Uri? u = Uri.tryParse(url);
  final Uri? b = Uri.tryParse(Api.base);
  return u != null &&
      b != null &&
      u.host.toLowerCase() == b.host.toLowerCase();
}

Future<bool> _openExternal(BuildContext context, String url) async {
  final Uri? u = Uri.tryParse(url);
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
  final bool? go = await showDialog<bool>(
    context: context,
    builder: (BuildContext ctx) => AlertDialog(
      title: const Text('打开外部链接？'),
      content: Text('即将离开 App 访问：\n${u.host}\n\n$u',
          style: const TextStyle(fontSize: 13)),
      actions: <Widget>[
        TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消')),
        FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('打开')),
      ],
    ),
  );
  if (go == true) {
    launchUrl(u, mode: LaunchMode.externalApplication);
  }
  return true;
}

String _hex(Color c) => '#${c.value.toRadixString(16).padLeft(8, '0').substring(2)}';

/// 服务端 HTML 统一渲染组件（字号取 fontScale，样式适配 .kw/.tag/表格/图片放大）
class HtmlView extends StatelessWidget {
  final String html;
  final void Function(String qid)? onQref;
  const HtmlView(this.html, {super.key, this.onQref});

  @override
  Widget build(BuildContext context) {
    final String body = onQref == null ? html : linkifyQrefs(html);
    return ValueListenableBuilder<double>(
      valueListenable: fontScale,
      builder: (BuildContext context, double fs, Widget? _) =>
          _HtmlBody(html: body.isEmpty ? '—' : body, fontSize: fs, onQref: onQref, inTable: false),
    );
  }
}

class _HtmlBody extends StatelessWidget {
  final String html;
  final double fontSize;
  final void Function(String qid)? onQref;
  final bool inTable;
  const _HtmlBody({
    required this.html,
    required this.fontSize,
    required this.onQref,
    required this.inTable,
  });

  void _zoom(BuildContext context, String raw) {
    final String url = raw.startsWith('http') ? raw : Api.base + raw;
    if (!_sameHost(url)) {
      toast(context, '已拦截站外图片');
      return;
    }
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withOpacity(0.92),
      builder: (BuildContext ctx) => GestureDetector(
        onTap: () => Navigator.of(ctx).pop(),
        child: InteractiveViewer(
          maxScale: 6,
          child: Image.network(url, fit: BoxFit.contain),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final Color pri = Theme.of(context).colorScheme.primary;
    final String hex = _hex(pri);
    return HtmlWidget(
      html,
      baseUrl: Uri.parse(Api.base),
      textStyle: TextStyle(fontSize: fontSize, height: 1.75),
      onTapUrl: (String url) {
        if (url.startsWith('qref://')) {
          onQref?.call(url.substring(7));
          return true;
        }
        return _openExternal(context, url);
      },
      onTapImage: (ImageMetadata meta) {
        if (meta.sources.isEmpty) return;
        _zoom(context, meta.sources.first.url);
      },
      customWidgetBuilder: (dynamic e) {
        if (inTable || e.localName != 'table') return null;
        final dynamic firstRow = e.querySelector('tr');
        final int cols = firstRow == null ? 0 : (firstRow.children.length as int);
        if (cols < 4) return null;
        final double w = (cols * 110.0).clamp(360.0, 1200.0).toDouble();
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: w,
            child: _HtmlBody(
              html: e.outerHtml as String,
              fontSize: fontSize,
              onQref: onQref,
              inTable: true,
            ),
          ),
        );
      },
      customStylesBuilder: (dynamic e) {
        final Set<String> cls = (e.classes as Iterable<dynamic>)
            .map((dynamic c) => c.toString())
            .toSet();
        if (cls.contains('kw')) {
          return <String, String>{
            'background-color': '${hex}22',
            'color': hex,
            'font-weight': '700',
            'padding': '0 4px',
            'border-radius': '4px',
          };
        }
        if (cls.contains('tag')) {
          return <String, String>{
            'background-color': '${hex}1f',
            'color': hex,
            'font-size': '0.85em',
            'padding': '0 6px',
            'border-radius': '6px',
          };
        }
        switch (e.localName as String) {
          case 'strong':
            return <String, String>{'color': hex, 'font-weight': '700'};
          case 'mark':
            return <String, String>{
              'background-color': '${hex}22',
              'color': hex,
              'font-weight': '700',
              'padding': '0 4px',
              'border-radius': '4px',
            };
          case 'h2':
          case 'h3':
            return <String, String>{'color': hex};
          case 'li':
            return <String, String>{'margin': '0 0 6px 0'};
          case 'blockquote':
            return <String, String>{
              'background-color': '${hex}14',
              'padding': '10px',
              'margin': '8px 0',
              'border-left': '3px solid $hex',
            };
          case 'table':
            return <String, String>{'font-size': '0.9em'};
          case 'th':
            return <String, String>{
              'background-color': '${hex}1f',
              'padding': '5px 8px',
            };
          case 'td':
            return <String, String>{'padding': '5px 8px'};
        }
        return null;
      },
    );
  }
}
