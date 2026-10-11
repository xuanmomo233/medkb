import { registerMock } from './registry'
import type { ChatAnswerResult, ChatMessage, ChatQuiz, ChatReply, ChatSendBody } from '@/api/types'

const now = () => new Date().toISOString()
const history: ChatMessage[] = [
  { role: 'user', content: '慢性心衰的治疗原则是什么？', html: '', created_at: now() },
  {
    role: 'assistant', created_at: now(), content: '',
    html: '<p>慢性心衰治疗要点：</p><ul><li><strong>ACEI/ARB/ARNI</strong>：改善预后</li><li><strong>β 受体阻滞剂</strong>：从小剂量开始</li><li><strong>醛固酮受体拮抗剂</strong>：EF 降低者</li><li><strong>利尿剂</strong>：缓解症状，不改善预后</li></ul>',
  },
]

const bank: Record<string, ChatQuiz & { answer: string; why: string }> = {
  L001: {
    qid: 'L001', system: '循环系统', multi: false, answer: 'B',
    stem_html: '<p>下列药物中，可改善慢性收缩性心力衰竭患者预后的是？</p>',
    options: [{ key: 'A', html: '<p>地高辛</p>' }, { key: 'B', html: '<p>美托洛尔</p>' }, { key: 'C', html: '<p>呋塞米</p>' }, { key: 'D', html: '<p>硝酸甘油</p>' }],
    why: 'β 受体阻滞剂可降低 HFrEF 死亡率；地高辛与利尿剂只缓解症状。',
  },
  S1024: {
    qid: 'S1024', system: '循环系统', multi: true, answer: 'ABD',
    stem_html: '<p>心力衰竭的代偿机制包括？</p>',
    options: [{ key: 'A', html: '<p>Frank-Starling 机制</p>' }, { key: 'B', html: '<p>心肌肥厚</p>' }, { key: 'C', html: '<p>副交感神经兴奋</p>' }, { key: 'D', html: '<p>神经体液机制激活</p>' }],
    why: '代偿包括 Frank-Starling、心肌肥厚与神经体液激活；交感神经兴奋而非副交感。',
  },
}

function reply(b: ChatSendBody): ChatReply {
  const m = b.message
  if (/考|出题|题/.test(m)) {
    const qs = /心衰|心力/.test(m) ? [bank.L001, bank.S1024] : [bank.L001]
    const quizzes = qs.map((q): ChatQuiz => ({ qid: q.qid, system: q.system, multi: q.multi, stem_html: q.stem_html, options: q.options }))
    const html = '<p>好的，来做 ' + quizzes.length + ' 道题检验一下：</p>'
    return { reply: '来做题', reply_html: html, quizzes }
  }
  if (/呼吸|梳理|重点/.test(m)) {
    const html = '<p>呼吸系统高频考点：</p><table><thead><tr><th>疾病</th><th>要点</th></tr></thead><tbody><tr><td>COPD</td><td>FEV1/FVC&lt;70%，长期氧疗 &gt;15h/d</td></tr><tr><td>支气管哮喘</td><td>可逆性气流受限，ICS 为首选</td></tr><tr><td>肺栓塞</td><td>CTPA 确诊，抗凝治疗</td></tr></tbody></table><ul><li>先掌握呼吸衰竭的血气标准</li><li>再对比肺炎各病原体特点</li></ul>'
    return { reply: '呼吸', reply_html: html, quizzes: [] }
  }
  if (/今天|学什么/.test(m)) {
    return { reply: '建议', reply_html: '<p>建议今日安排：</p><ul><li>先复习到期卡片</li><li>再做 20 道循环系统错题</li><li>最后用 AI 抽背收尾</li></ul>', quizzes: [] }
  }
  const extra = b.image ? '（已收到图片）' : b.file ? `（已收到文件 ${b.file.name}）` : ''
  const ctx = b.context ? `<p>结合你正在看的内容：<em>${b.context.slice(0, 40).replace(/</g, '&lt;')}</em></p>` : ''
  return { reply: '回答', reply_html: `${ctx}<p>关于「${m.replace(/</g, '&lt;').slice(0, 40)}」${extra}，核心是抓住<strong>病因—机制—表现—治疗</strong>四步框架。需要我出题巩固吗？</p>`, quizzes: [] }
}

let calls = 0
registerMock('GET', '/chat/history', () => history)
registerMock('POST', '/chat/messages', ({ body }) => {
  const b = body as ChatSendBody
  if (++calls % 7 === 0) throw new Error('提问太频繁了，请稍后再试')
  history.push({ role: 'user', content: b.message, html: '', created_at: now() })
  const r = reply(b)
  history.push({ role: 'assistant', content: r.reply, html: r.reply_html, created_at: now() })
  return r
})
registerMock('POST', '/chat/answer', ({ body }): ChatAnswerResult => {
  const { qid, answer } = body as { qid: string; answer: string }
  const q = bank[qid]
  const correct = !!q && q.answer === answer
  const html = `<p>${correct ? '✅ 回答正确！' : `❌ 正确答案是 <strong>${q?.answer ?? '?'}</strong>。`}</p><p>${q?.why ?? ''}</p>`
  return { correct, answer: q?.answer ?? '', qid, reply: html, reply_html: html }
})
registerMock('DELETE', '/chat/history', () => { history.length = 0 })
