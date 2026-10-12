import 'package:flutter/material.dart';

/// 全站统一下拉刷新：
/// - 只响应「手指仍在屏幕上」的拖拽 overscroll；惯性滚动（fling/回弹）
///   产生的 OverscrollNotification.dragDetails == null，一律忽略——
///   这是快速滚到顶误触发刷新的主因。
/// - displacement 80（默认 40 的两倍）：需要更明确的一段下拉才触发。
class AppRefreshIndicator extends RefreshIndicator {
  const AppRefreshIndicator({
    super.key,
    required super.onRefresh,
    required super.child,
  }) : super(displacement: 80, notificationPredicate: _predicate);

  static bool _predicate(ScrollNotification n) {
    if (n.depth != 0) return false;
    if (n is OverscrollNotification && n.dragDetails == null) return false;
    return true;
  }
}
