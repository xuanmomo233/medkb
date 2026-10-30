export function textbookPdfUrl(sourceKey) {
  return `/api/textbooks/${encodeURIComponent(sourceKey)}.pdf`
}

export function errorMessage(error) {
  const message = error instanceof Error ? error.message : String(error)
  if (/401|403|unauthori[sz]ed|forbidden/i.test(message)) return '登录状态无效或已过期，请重新登录后再阅读。'
  if (/404|not found|missing pdf/i.test(message)) return '该教材文件尚未上传或暂不可用，请联系管理员检查教材资源。'
  if (/fetch|network|failed to load|连接/i.test(message)) return '教材加载失败，请检查网络连接后重试。'
  return `教材读取失败：${message}`
}
