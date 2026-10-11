import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'models.dart' show VersionInfo;
import 'widgets/widgets.dart';

/// APP 内自更新：下载 /app.apk 并拉起系统安装器。
class SelfUpdate {
  SelfUpdate._();

  /// 有新版本时弹出确认框，确认后进入下载流程。
  static Future<void> prompt(BuildContext context, VersionInfo v) async {
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: const Text('发现新版本'),
        content: Text(
            '${v.note}\n（当前 build ${Api.appBuild} → 最新 build ${v.build}）'),
        actions: <Widget>[
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('稍后')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('立即更新')),
        ],
      ),
    );
    if (ok == true && context.mounted) await downloadFlow(context, v.build);
  }

  /// 带进度条的下载；完成后拉起安装器。
  static Future<void> downloadFlow(BuildContext context, [int? build]) async {
    // ?v= 按版本号做缓存穿透，防 CDN 发旧包
    final Uri apk =
        Uri.parse('${Api.base}/app.apk?v=${build ?? Api.appBuild}');
    final ValueNotifier<double> prog = ValueNotifier<double>(0);
    final ValueNotifier<String> stat = ValueNotifier<String>('连接中…');
    bool cancel = false;
    BuildContext? dlg;

    unawaited(showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext c) {
        dlg = c;
        return PopScope(
          canPop: false,
          child: AlertDialog(
            title: const Text('下载更新包'),
            content: ValueListenableBuilder<double>(
              valueListenable: prog,
              builder: (_, double v, __) => Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  LinearProgressIndicator(value: v > 0 ? v : null),
                  const SizedBox(height: 12),
                  ValueListenableBuilder<String>(
                    valueListenable: stat,
                    builder: (_, String t, __) => Text(t,
                        style: const TextStyle(fontSize: 13)),
                  ),
                ],
              ),
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () {
                  cancel = true;
                  Navigator.of(c).pop();
                },
                child: const Text('取消'),
              ),
            ],
          ),
        );
      },
    ));

    File? f;
    try {
      final http.Request req =
          http.Request('GET', apk);
      final http.StreamedResponse res = await req.send();
      if (res.statusCode != 200) throw 'HTTP ${res.statusCode}';
      final int total = res.contentLength ?? 0;
      final Directory dir = await getTemporaryDirectory();
      f = File('${dir.path}/medkb-update.apk');
      final IOSink sink = f.openWrite();
      int got = 0;
      await for (final List<int> chunk in res.stream) {
        if (cancel) break;
        sink.add(chunk);
        got += chunk.length;
        prog.value = total > 0 ? got / total : 0;
        stat.value =
            '${(got / 1048576).toStringAsFixed(1)} / ${(total / 1048576).toStringAsFixed(1)} MB';
      }
      await sink.close();
      _close(dlg);
      if (cancel) {
        await f.delete().catchError((_) => f!);
        return;
      }
      stat.value = '完成，调起安装器…';
      final OpenResult r = await OpenFilex.open(f.path,
          type: 'application/vnd.android.package-archive');
      if (r.type != ResultType.done && context.mounted) {
        // 安装器拉起失败：退回浏览器下载
        await launchUrl(apk, mode: LaunchMode.externalApplication);
        if (context.mounted) toast(context, '已退回浏览器下载，请在下载目录手动安装');
      }
    } catch (e) {
      _close(dlg);
      if (!cancel && context.mounted) toast(context, '下载失败：$e');
    } finally {
      prog.dispose();
      stat.dispose();
    }
  }

  static void _close(BuildContext? dlg) {
    final BuildContext? c = dlg;
    if (c != null && c.mounted) Navigator.of(c).pop();
  }
}
