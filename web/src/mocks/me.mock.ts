import { registerMock } from './registry'

registerMock('GET', '/version', () => ({ build: 128, note: '新增薄弱点阈值设置；AI 陪学支持图片与文件；修复若干排版问题。' }))

