import type { ChapterDetail, ContentTree, SearchHit, SearchKind } from '@/api/types'
import { cards } from './cards.mock'
import { registerMock } from './registry'

type Row = [subject: string, title: string, points: string[]]

const ROWS: Row[] = [
  ['生理学', '细胞的基本功能', ['静息电位主要由 K⁺ 外流形成', '动作电位上升支为 Na⁺ 内流，具有“全或无”特点', '易化扩散包括通道转运与载体转运']],
  ['生理学', '血液循环', ['心输出量 = 搏出量 × 心率', '窦房结自律性最高，为正常起搏点', '动脉血压收缩压反映搏出量，舒张压反映外周阻力']],
  ['生理学', '呼吸', ['肺通气的直接动力是肺内压与大气压之差', '肺表面活性物质由 II 型肺泡细胞分泌', '氧解离曲线右移表示 Hb 对 O₂ 亲和力降低']],
  ['生理学', '消化和吸收', ['胃酸由壁细胞分泌，盐酸分泌的最强刺激为组胺', '小肠是吸收的主要部位', '胆盐的肠肝循环']],
  ['生物化学', '蛋白质的结构与功能', ['二级结构：α-螺旋、β-折叠、β-转角、无规卷曲', '蛋白质变性不涉及肽键断裂', '等电点时溶解度最小']],
  ['生物化学', '酶', ['竞争性抑制：Km 增大，Vmax 不变', '非竞争性抑制：Km 不变，Vmax 降低', '酶原激活的本质是活性中心形成或暴露']],
  ['生物化学', '糖代谢', ['糖酵解的关键酶：己糖激酶、磷酸果糖激酶-1、丙酮酸激酶', '三羧酸循环一次生成 10 分子 ATP', '糖异生的关键酶：丙酮酸羧化酶、PEPCK、果糖二磷酸酶-1、葡萄糖-6-磷酸酶']],
  ['病理学', '细胞和组织的适应与损伤', ['适应：萎缩、肥大、增生、化生', '坏死的类型：凝固性、液化性、干酪样、脂肪、坏疽', '凋亡是程序性细胞死亡，不引起炎症反应']],
  ['病理学', '炎症', ['急性炎症以中性粒细胞浸润为主', '慢性炎症以淋巴细胞、浆细胞、巨噬细胞浸润为主', '肉芽肿性炎的代表：结核、结节病']],
  ['病理学', '肿瘤', ['良恶性肿瘤的区别：异型性、生长方式、转移', '癌与肉瘤的区别：上皮来源与间叶来源', '癌前病变与原位癌']],
  ['诊断学', '症状学', ['咯血与呕血的鉴别', '呼吸困难分类：肺源性、心源性、中毒性、血源性、神经精神性', '黄疸分类：溶血性、肝细胞性、胆汁淤积性']],
  ['诊断学', '心电图', ['P 波代表心房除极', 'QRS 波代表心室除极', 'ST 段抬高提示心肌损伤，病理性 Q 波提示心肌梗死']],
  ['内科学', '心力衰竭', ['诊断：症状 + 体征 + BNP + LVEF', '药物治疗“金三角”：ACEI/ARNI、β 受体阻滞剂、醛固酮拮抗剂', '急性左心衰：吗啡、利尿剂、血管扩张剂']],
  ['内科学', '肺炎', ['肺炎链球菌肺炎：铁锈色痰，首选青霉素', '支原体肺炎：青少年，大环内酯类', '重症肺炎判断标准']],
  ['内科学', '消化性溃疡', ['GU 与 DU 的鉴别', 'Hp 根除四联疗法', '并发症：出血、穿孔、幽门梗阻、癌变']],
  ['内科学', '糖尿病', ['诊断标准：空腹血糖 ≥ 7.0 mmol/L 或 OGTT 2 h ≥ 11.1 mmol/L', 'DKA 的治疗：补液为首要措施', '二甲双胍为 2 型糖尿病首选药物']],
  ['外科学', '水电解质代谢紊乱', ['高渗性缺水：口渴明显，血钠 > 150 mmol/L', '低钾血症：心电图 U 波', '补钾原则：见尿补钾，浓度 < 0.3%']],
  ['外科学', '外科休克', ['低血容量性休克：补充血容量是关键', '感染性休克：早期液体复苏与抗感染', '中心静脉压（CVP）指导补液']],
  ['外科学', '急性阑尾炎', ['转移性右下腹痛', '麦氏点压痛、反跳痛', '手术方式首选腹腔镜阑尾切除']],
  ['医学人文', '医学伦理学基本原则', ['尊重、不伤害、有利、公正四原则', '知情同意的要素', '保密原则及其例外']],
  ['医学人文', '医患关系', ['萨斯-荷伦德的三种模式：主动-被动型、指导-合作型、共同参与型', '医患沟通技巧', '医疗纠纷的预防与处理']],
]

const SUBJECT_SYSTEM: Record<string, string[]> = {
  生理学: ['循环系统', '呼吸系统', '消化系统'],
  生物化学: ['基础生化'],
  病理学: ['总论', '各论'],
  诊断学: ['症状学', '检查诊断'],
  内科学: ['循环系统', '呼吸系统', '消化系统', '内分泌系统'],
  外科学: ['外科总论', '腹部外科'],
  医学人文: ['医学伦理', '医患关系'],
}

const mindmaps = ROWS.map(([subject, title], i) => ({ id: i + 1, subject, title }))
const notes = ROWS.map(([subject, title], i) => ({ id: i + 101, subject, title }))
const questionChapters = ROWS.map(([subject, chapter], i) => {
  const systems = SUBJECT_SYSTEM[subject]
  return { chapter, subject_dir: subject, system: systems[i % systems.length] }
})

const tree = (): ContentTree => ({ mindmaps, notes, question_chapters: questionChapters })

function chapterOf(id: number): ChapterDetail | null {
  const isNote = id > 100
  const row = ROWS[(isNote ? id - 101 : id - 1)]
  if (!row) return null
  const [subject, title, points] = row
  const html = `<h2>${title}</h2><p>本章是 <mark class="kw">${subject}</mark> 的${isNote ? '考点精要' : '思维导图'}内容，建议先通读框架，再结合背卡与题库巩固。</p>`
    + `<h3>核心考点</h3><ul>${points.map((p) => `<li>${p}</li>`).join('')}</ul>`
    + `<blockquote>记忆提示：先掌握<strong>定义与诊断标准</strong>，再记忆<strong>鉴别要点</strong>与<strong>首选治疗</strong>。</blockquote>`
    + `<h3>易混淆对比</h3><table><thead><tr><th>项目</th><th>要点一</th><th>要点二</th></tr></thead><tbody>`
    + `<tr><td>特点</td><td>${points[0]}</td><td>${points[1]}</td></tr><tr><td>备注</td><td>高频考点 <span class="tag">必背</span></td><td>近五年多次考查</td></tr></tbody></table>`
  return {
    id, title, subject, html,
    meta: { 考频: isNote ? '高频' : '中频', 标签: `${subject} · ${isNote ? '精要' : '导图'}`, 题量: String(8 + (id % 7) * 3) },
    pages: isNote || id % 2 === 0 ? [] : [id, id + 1, id + 2].map((n) => n),
  }
}

registerMock('GET', '/content/tree', tree)
registerMock('GET', '/content/chapters/{id}', ({ params }) => {
  const c = chapterOf(Number(params.id))
  if (!c) throw new Error('章节不存在')
  return c
})

const QUESTIONS = [
  { id: 1001, title: '心力衰竭患者使用洋地黄的指征', snippet: '慢性收缩性心力衰竭伴快速心房颤动者，洋地黄类药物疗效确切；心衰合并预激综合征伴房颤者禁用。' },
  { id: 1002, title: '下列哪项是肺炎链球菌肺炎的典型痰液特点', snippet: '典型表现为铁锈色痰，病原菌为革兰阳性双球菌，首选青霉素 G 治疗。' },
  { id: 1003, title: '胃溃疡的好发部位', snippet: '胃溃疡好发于胃小弯和胃角，疼痛多在进餐后 0.5~1 小时出现，需与胃癌鉴别。' },
  { id: 1004, title: '竞争性抑制作用的特点', snippet: '竞争性抑制剂与底物结构相似，Km 增大而 Vmax 不变，增加底物浓度可解除抑制。' },
  { id: 1005, title: '糖尿病酮症酸中毒的首要治疗措施', snippet: '首要措施是补液，其次小剂量胰岛素持续静滴，补钾并纠正电解质紊乱。' },
  { id: 1006, title: '急性阑尾炎最典型的腹痛特点', snippet: '典型表现为转移性右下腹痛，起初在上腹或脐周，数小时后转移并固定于右下腹。' },
]

registerMock('GET', '/search', ({ query }) => {
  const q = String(query.q ?? '').trim().toLowerCase()
  const kind = query.kind as SearchKind | undefined
  if (!q) return []
  const hit = (...t: string[]) => t.some((x) => x.toLowerCase().includes(q))
  const out: SearchHit[] = []
  if (!kind || kind === 'question') {
    for (const x of QUESTIONS) if (hit(x.title, x.snippet)) out.push({ kind: 'question', ...x, state: x.id % 3 === 0 ? 'again' : x.id % 3 === 1 ? 'mastered' : '', starred: x.id === 1002 })
  }
  if (!kind || kind === 'card') {
    for (const c of cards()) {
      const text = c.body_html.replace(/<[^>]+>/g, ' ')
      if (hit(c.term, c.hint, text)) out.push({ kind: 'card', id: c.id, title: c.term, snippet: `${c.hint}。${text.replace(/\s+/g, ' ').trim()}`.slice(0, 140), state: c.state, starred: c.starred })
    }
  }
  if (!kind || kind === 'chapter') {
    for (const [i, [subject, title, points]] of ROWS.entries()) {
      if (hit(title, subject, ...points)) out.push({ kind: 'chapter', id: i + 101, title: `${subject} · ${title}`, snippet: points.join('；'), state: '', starred: false })
    }
  }
  return out
})
