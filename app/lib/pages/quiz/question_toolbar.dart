import 'package:flutter/material.dart';
import '../../api.dart';
import '../../models.dart' hide Card;
import '../../theme.dart';
import 'quiz_session.dart';

class QuestionToolbar extends StatelessWidget {
  final bool starred;
  final String state;
  final bool canRedo;
  final void Function(MarkKind kind) onToggle;
  final VoidCallback onRedo;
  final VoidCallback onNotes;
  final VoidCallback onEdit;
  const QuestionToolbar({
    super.key,
    required this.starred,
    required this.state,
    required this.canRedo,
    required this.onToggle,
    required this.onRedo,
    required this.onNotes,
    required this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    final AppColors c = AppColors.of(context);
    return Wrap(
      spacing: 4,
      runSpacing: 0,
      children: <Widget>[
        _Btn(
          icon: starred ? Icons.star : Icons.star_border,
          label: starred ? '已收藏' : '收藏',
          color: starred ? c.warn : null,
          onTap: () => onToggle(MarkKind.star),
        ),
        _Btn(
          icon: state == ProgressState.again
              ? Icons.bookmark
              : Icons.bookmark_border,
          label: state == ProgressState.again ? '移出错题' : '加入错题本',
          color: state == ProgressState.again ? c.bad : null,
          onTap: () => onToggle(MarkKind.wrong),
        ),
        _Btn(
          icon: state == ProgressState.mastered
              ? Icons.verified
              : Icons.verified_outlined,
          label: state == ProgressState.mastered ? '已掌握' : '完全掌握',
          color: state == ProgressState.mastered ? c.good : null,
          onTap: () => onToggle(MarkKind.master),
        ),
        _Btn(
          icon: state == ProgressState.plan
              ? Icons.event_available
              : Icons.event_note_outlined,
          label: state == ProgressState.plan ? '取消复习' : '加入复习',
          color: state == ProgressState.plan ? c.info : null,
          onTap: () => onToggle(MarkKind.plan),
        ),
        _Btn(icon: Icons.edit_note, label: '笔记', onTap: onNotes),
        if (Api.admin)
          _Btn(icon: Icons.edit_outlined, label: '编辑', onTap: onEdit),
        if (canRedo) _Btn(icon: Icons.replay, label: '重做', onTap: onRedo),
      ],
    );
  }
}

class _Btn extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color? color;
  final VoidCallback onTap;
  const _Btn({
    required this.icon,
    required this.label,
    required this.onTap,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final Color fg = color ?? Theme.of(context).colorScheme.onSurfaceVariant;
    return TextButton.icon(
      style: TextButton.styleFrom(
        foregroundColor: fg,
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 10),
      ),
      onPressed: onTap,
      icon: Icon(icon, size: 20),
      label: Text(label, style: const TextStyle(fontSize: 13)),
    );
  }
}
