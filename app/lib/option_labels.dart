final RegExp _optionLabel = RegExp(r'^[A-Z]$');

String answerOptionLetters(String answer) {
  final String normalized = String.fromCharCodes(answer.runes.map((int code) =>
      code >= 0xff21 && code <= 0xff3a || code >= 0xff41 && code <= 0xff5a ? code - 0xfee0 : code))
      .toUpperCase().trim();
  if (!RegExp(r'^[A-Z]+(?:[\s,，、/;；]+[A-Z]+)*$').hasMatch(normalized)) return '';
  final List<String> letters = RegExp(r'[A-Z]').allMatches(normalized)
      .map((RegExpMatch match) => match.group(0)!).toSet().toList()..sort();
  return letters.join();
}

List<String> sequentialOptionLabels(int count) {
  if (count < 0 || count > 26) throw const FormatException('选项数量须在 0–26 之间');
  return List<String>.generate(count, (int i) => String.fromCharCode(65 + i));
}

List<String> readOptionLabels(Object? raw, int count) {
  if (count < 0 || count > 26) throw const FormatException('选项数量须在 0–26 之间');
  if (raw == null || raw is List && raw.isEmpty) return sequentialOptionLabels(count);
  if (raw is! List || raw.length != count ||
      raw.any((dynamic label) => label is! String || !_optionLabel.hasMatch(label)) ||
      raw.toSet().length != count) {
    throw const FormatException('选项标签须为不重复的 A–Z 字母，并与选项一一对应');
  }
  return List<String>.from(raw);
}

class LabeledOptions {
  final List<String> options;
  final List<String> labels;
  const LabeledOptions(this.options, this.labels);
}

String formatOptionLines(List<String> options, List<String> labels) =>
    List<String>.generate(options.length, (int i) => '${labels[i]}. ${options[i]}').join('\n');

LabeledOptions parseOptionLines(String text, List<String> previousLabels) {
  if (text.trim().isEmpty) return const LabeledOptions(<String>[], <String>[]);
  final List<String> lines = text.split('\n');
  final RegExp prefix = RegExp(r'^([A-Z])[.、．]\s*(.*)$', caseSensitive: false);
  final List<RegExpMatch?> matches = lines.map((String line) => prefix.firstMatch(line.trim())).toList();
  if (matches.every((RegExpMatch? match) => match != null)) {
    final List<String> labels = matches.map((RegExpMatch? match) => match!.group(1)!.toUpperCase()).toList();
    return LabeledOptions(matches.map((RegExpMatch? match) => match!.group(2)!.trim()).toList(),
        readOptionLabels(labels, lines.length));
  }
  if (matches.any((RegExpMatch? match) => match != null)) {
    throw const FormatException('请为每个选项保留字母前缀，或全部使用无前缀文本');
  }
  if (lines.length == previousLabels.length) {
    return LabeledOptions(lines.map((String line) => line.trim()).toList(), List<String>.of(previousLabels));
  }
  final List<String> previousSequence = sequentialOptionLabels(previousLabels.length);
  for (int i = 0; i < previousLabels.length; i++) {
    if (previousLabels[i] != previousSequence[i]) {
      throw const FormatException('非连续标签的选项数量改变时，请为每行填写原始字母前缀');
    }
  }
  return LabeledOptions(lines.map((String line) => line.trim()).toList(), sequentialOptionLabels(lines.length));
}
