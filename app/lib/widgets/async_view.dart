import 'package:flutter/material.dart';
import '../api.dart';
import 'cache_banner.dart';
import 'load_error.dart';
import 'loading_view.dart';
import 'toast.dart';

/// 统一的异步加载视图：loading / 错误+重试 / 数据。
/// - builder 的 refresh 回调会静默刷新（保留旧数据，失败只弹 toast），可配合 RefreshIndicator(onRefresh: refresh)
/// - reloadKey 变化时重新加载（显示 loading）
/// - showCacheBanner 为 true 且数据来自离线缓存时，顶部加「离线数据」角标；此时父级须有确定高度
///   （在 ListView 等无界高度容器内使用请设 showCacheBanner: false）
class AsyncView<T> extends StatefulWidget {
  final Future<T> Function() loader;
  final Widget Function(BuildContext context, T data, Future<void> Function() refresh) builder;
  final Object? reloadKey;
  final bool showCacheBanner;
  const AsyncView({
    super.key,
    required this.loader,
    required this.builder,
    this.reloadKey,
    this.showCacheBanner = true,
  });

  @override
  State<AsyncView<T>> createState() => AsyncViewState<T>();
}

/// 公开以便外部通过 GlobalKey<AsyncViewState<T>> 调 reload()
class AsyncViewState<T> extends State<AsyncView<T>> {
  T? _data;
  bool _has = false;
  Object? _err;
  bool _fromCache = false;
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    _load(silent: false);
  }

  @override
  void didUpdateWidget(covariant AsyncView<T> oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.reloadKey != widget.reloadKey) _load(silent: false);
  }

  /// 静默刷新
  Future<void> reload() => _load(silent: true);

  Future<void> _load({required bool silent}) async {
    final int my = ++_seq;
    if ((!silent || !_has) && (_has || _err != null)) {
      setState(() {
        _err = null;
        _has = false;
      });
    }
    try {
      final T d = await widget.loader();
      if (!mounted || my != _seq) return;
      setState(() {
        _data = d;
        _has = true;
        _err = null;
        _fromCache = Api.lastFromCache;
      });
    } catch (e) {
      if (!mounted || my != _seq) return;
      if (_has) {
        toast(context, errText(e));
      } else {
        setState(() {
          _err = e;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final Object? err = _err;
    if (err != null) {
      return LoadError(msg: errText(err), onRetry: () => _load(silent: false));
    }
    if (!_has) return const LoadingView();
    final Widget body = widget.builder(context, _data as T, reload);
    if (!widget.showCacheBanner || !_fromCache) return body;
    return Column(
      children: <Widget>[
        const CacheBanner(),
        Expanded(child: body),
      ],
    );
  }
}
