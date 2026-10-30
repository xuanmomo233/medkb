import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../api.dart';
import '../../endpoints.dart';
import '../../models.dart';

class ScheduleSession extends ChangeNotifier {
  final List<ScheduleItem> items;
  final String day;
  late final String _key =
      Api.prefKey('schedule-study', '${Api.base}|${Api.token}|$day');
  final Map<int, Map<String, dynamic>> _answers = {};
  final Map<int, String> ratings = {};
  final Set<int> flippedCards = {};
  static Future<void> _writes = Future<void>.value();
  int index;
  bool _disposed = false;
  bool _refreshing = false;
  VoidCallback? onOpenJump;
  ValueChanged<int>? onNavigate;

  ScheduleSession(
      {required List<ScheduleItem> items,
      required this.index,
      required this.day})
      : items = List<ScheduleItem>.of(items);

  String _signature(Question q) =>
      jsonEncode([q.id, q.optionsHtml, q.optionLabels, q.answer]);

  Future<void> load() async {
    final key = _key;
    try {
      await _writes;
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(key);
      if (raw == null) return;
      final data = asMap(jsonDecode(raw));
      asMap(data['answers']).forEach((k, v) {
        final id = int.tryParse(k);
        if (id != null) _answers[id] = asMap(v);
      });
      asMap(data['ratings']).forEach((k, v) {
        final id = int.tryParse(k);
        if (id != null &&
            v is String &&
            [MarkAction.rateAgain, MarkAction.rateHard, MarkAction.rateGood]
                .contains(v)) ratings[id] = v;
      });
      final flips = data['flipped'];
      if (flips is List)
        flippedCards.addAll(flips.whereType<num>().map((v) => v.toInt()));
    } catch (_) {/* 缓存不可用时仍可开始日程。 */}
  }

  void start() {
    Api.studyRevision.addListener(refresh);
    unawaited(refresh());
  }

  Future<void> refresh() async {
    if (_disposed || _refreshing) return;
    _refreshing = true;
    try {
      final data = await Endpoints.scheduleToday();
      if (_disposed || data.day != day) return;
      for (var i = 0; i < items.length; i++) {
        final old = items[i];
        final matches = data.items.where((item) => item.matchesId(old.id));
        if (matches.isEmpty) continue;
        final latest = matches.first;
        items[i] = ScheduleItem(
            id: old.id,
            sourceIds: old.sourceIds,
            itemType: old.itemType,
            itemId: old.itemId,
            reason: old.reason,
            title: latest.title,
            done: latest.done);
      }
      notifyListeners();
    } catch (_) {/* 刷新失败时保留当前队列及作答状态。 */} finally {
      _refreshing = false;
    }
  }

  Map<String, dynamic>? answerFor(Question q) {
    final a = _answers[q.id];
    if (a == null) return null;
    if (a['signature'] != _signature(q)) {
      clearAnswer(q.id);
      return null;
    }
    final picked = a['picked'];
    if (picked is! String ||
        picked.isEmpty ||
        !picked.split('').every(q.optionLabels.contains) ||
        a['judged'] is! bool ||
        (a['judged'] == true && a['correct'] is! bool)) return null;
    return a;
  }

  Map<String, dynamic>? savedAnswer(int id) => _answers[id];

  void saveAnswer(Question q, String picked, bool judged, bool? correct) {
    if (picked.isEmpty) {
      clearAnswer(q.id);
      return;
    }
    _answers[q.id] = {
      'signature': _signature(q),
      'picked': picked,
      'judged': judged,
      'correct': correct
    };
    _persist();
    if (!_disposed) notifyListeners();
  }

  void clearAnswer(int id) {
    _answers.remove(id);
    _persist();
    if (!_disposed) notifyListeners();
  }

  void saveCard(int id, {String? rating, bool? flipped}) {
    if (rating != null) ratings[id] = rating;
    if (flipped == true) flippedCards.add(id);
    if (flipped == false) flippedCards.remove(id);
    _persist();
    if (!_disposed) notifyListeners();
  }

  void _persist() {
    final key = _key;
    final value = jsonEncode({
      'answers': _answers.map((k, v) => MapEntry('$k', v)),
      'ratings': ratings.map((k, v) => MapEntry('$k', v)),
      'flipped': flippedCards.toList(),
    });
    _writes = _writes.catchError((Object _) {}).then((_) async {
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(key, value);
      } catch (_) {}
    });
  }

  void go(int next) {
    if (!_disposed && next >= 0 && next < items.length && next != index)
      onNavigate?.call(next);
  }

  void setIndex(int value) {
    if (_disposed || index == value) return;
    index = value;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    Api.studyRevision.removeListener(refresh);
    onNavigate = null;
    onOpenJump = null;
    super.dispose();
  }
}
