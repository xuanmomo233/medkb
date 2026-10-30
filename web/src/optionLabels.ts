export const OPTION_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

/** Empty metadata is the legacy contract; invalid explicit metadata is not remapped. */
export function optionLabels(count: number, explicit?: readonly string[] | null): string[] {
  if (!Number.isInteger(count) || count < 0 || count > 26) return []
  if (!explicit?.length) return [...OPTION_ALPHABET].slice(0, count)
  if (explicit.length !== count || new Set(explicit).size !== count || explicit.some((label) => !/^[A-Z]$/.test(label))) return []
  return [...explicit]
}

export function answerLabels(answer: string, labels: readonly string[]): string[] | null {
  const normalized = answer.normalize('NFKC').toUpperCase().trim()
  if (!/^[A-Z]+(?:[\s,，、/;；]+[A-Z]+)*$/.test(normalized)) return null
  const picked = [...new Set(normalized.match(/[A-Z]/g) ?? [])]
  return picked.every((label) => labels.includes(label)) ? picked : null
}

export function pickedIndices(picked: string, labels: readonly string[]): number[] {
  const selected = answerLabels(picked, labels)
  if (!selected) return []
  return selected.map((label) => labels.indexOf(label))
}

export function optionKey(key: string, labels: readonly string[]): string | undefined {
  if (/^[1-9]$/.test(key)) return labels[Number(key) - 1]
  if (key === '0') return labels[9]
  const letter = key.toUpperCase()
  return key.length === 1 && labels.includes(letter) ? letter : undefined
}

export function formatLabeledOptions(options: readonly string[], labels?: readonly string[]): string {
  const keys = optionLabels(options.length, labels)
  return options.map((option, i) => `${keys[i] ?? '?'}. ${option}`).join('\n')
}

/** Every row carries its original label, so gaps cannot silently renumber answers. */
export function parseLabeledOptions(value: string): { options: string[]; option_labels: string[] } {
  if (!value.trim()) return { options: [], option_labels: [] }
  const options: string[] = []
  const labels: string[] = []
  for (const line of value.split(/\r?\n/)) {
    const match = /^\s*([A-ZＡ-Ｚ])[.、．)）:：]\s*(.*)$/i.exec(line)
    if (!match) throw new Error('每行选项须保留 A. 这样的字母标签')
    labels.push(match[1].normalize('NFKC').toUpperCase())
    options.push(match[2].trim())
  }
  if (labels.length > 26 || new Set(labels).size !== labels.length) throw new Error('选项标签须为不重复的 A–Z，最多26项')
  return { options, option_labels: labels }
}

export function questionOptionPatch(original: { options: string[]; option_labels?: string[]; answer: string }, text: string, answer: string): { options?: string[]; option_labels?: string[]; answer?: string } {
  const parsed = parseLabeledOptions(text)
  const changed = JSON.stringify(parsed.options) !== JSON.stringify(original.options)
    || JSON.stringify(parsed.option_labels) !== JSON.stringify(optionLabels(original.options.length, original.option_labels))
  if ((changed || answer !== original.answer) && parsed.options.length && !answerLabels(answer, parsed.option_labels)) throw new Error('正确答案必须使用现有选项标签')
  if (changed) return { ...parsed, ...(answer !== original.answer ? { answer } : {}) }
  return answer !== original.answer ? { answer } : {}
}
