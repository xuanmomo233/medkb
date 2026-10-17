import type { Card, CardPartIndex, CardQuery, MarkAction, ProgressState } from '@/api/types'
import { NEXT, registerMock } from './registry'

registerMock('GET', '/cards/{id}/sources', () => [])

const fmt = (t: string) => t.replace(/\*\*(.+?)\*\*/g, '<mark class="kw">$1</mark>').replace(/\[\[(.+?)\]\]/g, '<span class="tag">$1</span>')
const ul = (...li: string[]) => `<ul>${li.map((x) => `<li>${fmt(x)}</li>`).join('')}</ul>`
const table = (head: string[], rows: string[][]) =>
  `<table><thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${fmt(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`

type Seed = [term: string, hint: string, body: string]
let nextId = 1
const cardDb: Card[] = []
function part(subject: string, partName: string, section: string, seeds: Seed[]) {
  for (const [term, hint, body] of seeds) {
    cardDb.push({ id: nextId++, subject, part: partName, section, term, term_html: term.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">'), hint, body_html: body, state: '', starred: false })
  }
}

part('内科学', '循环系统', '心力衰竭', [
  ['心衰的诊断标准', '症状、体征与客观依据', ul('**症状**：呼吸困难、乏力、液体潴留 [[高频]]', '**体征**：肺部啰音、颈静脉怒张、肝颈静脉反流征阳性、下肢水肿', '**客观依据**：BNP > 100 pg/ml 或 NT-proBNP > 300 pg/ml；超声心动图 **LVEF < 40%**')],
  ['心衰的 NYHA 心功能分级', 'I~IV 级各自的活动耐量', table(['分级', '表现'], [['I 级', '日常活动不受限'], ['II 级', '日常活动出现症状，体力活动轻度受限'], ['III 级', '低于日常活动即出现症状，明显受限'], ['IV 级', '休息时也有症状，**不能从事任何体力活动**']])],
  ['急性左心衰的处理', '“端坐、吸氧、镇静、利尿、强心、扩血管”', ul('体位：**端坐位**，双腿下垂', '高流量吸氧，必要时无创通气', '**吗啡** 3~5 mg 静注（休克、昏迷、COPD 禁用）', '**呋塞米** 20~40 mg 静注', '硝普钠/硝酸甘油扩血管，血压低时慎用')],
  ['慢性心衰的“金三角”药物', 'ACEI、β 受体阻滞剂、醛固酮拮抗剂', ul('**ACEI/ARB/ARNI**：降低病死率，干咳换 ARB', '**β 受体阻滞剂**：从小剂量开始，病情稳定后使用，禁用于急性失代偿期', '**醛固酮受体拮抗剂**：监测血钾', '**SGLT2 抑制剂**：新增的基石药物')],
  ['左心衰与右心衰的鉴别', '肺循环淤血 vs 体循环淤血', table(['项目', '左心衰', '右心衰'], [['主要表现', '**肺淤血**、呼吸困难', '**体循环淤血**、水肿'], ['体征', '肺底湿啰音、奔马律', '颈静脉怒张、肝大、下肢水肿'], ['常见病因', '高血压、冠心病、主动脉瓣病变', '肺心病、左心衰继发']])],
  ['洋地黄中毒的表现与处理', '胃肠道、神经、心律失常', ul('胃肠道：**恶心呕吐**为早期表现', '神经系统：视物模糊、黄绿视', '心律失常：**室性早搏二联律**最常见，快速房性心动过速伴房室传导阻滞', '处理：停药，补钾，**苯妥英钠/利多卡因**，缓慢性心律失常用阿托品')],
  ['心衰的常见诱因', '感染最常见', ul('**呼吸道感染**是最常见诱因', '心律失常（尤其快速房颤）', '血容量增加、过度劳累与情绪激动', '妊娠与分娩、贫血、甲亢', '药物：负性肌力药物、NSAIDs')],
  ['舒张性心力衰竭的特点', 'LVEF 正常的心衰', ul('LVEF **≥ 50%**，但舒张功能减退', '多见于老年、高血压、肥厚型心肌病', '避免使用过多利尿剂和血管扩张剂', '禁用正性肌力药（肥厚型心肌病）', '治疗重点：控制血压与心率')],
  ['利尿剂在心衰中的应用', '消除水肿，不降低病死率（螺内酯除外）', ul('**袢利尿剂**：呋塞米，首选', '噻嗪类：轻度水肿，肾功能差时无效', '保钾利尿剂：螺内酯、氨苯蝶啶', '常见副作用：低钾、低镁、高尿酸')],
])

part('内科学', '呼吸系统', '肺炎', [
  ['肺炎链球菌肺炎', '铁锈色痰、大叶性实变', ul('病原：**肺炎链球菌**，革兰染色阳性双球菌 [[高频]]', '典型表现：寒战高热、胸痛、**铁锈色痰**', '影像：肺叶或肺段**实变**，可见支气管充气征', '首选 **青霉素 G**；过敏者用呼吸喹诺酮或多西环素')],
  ['葡萄球菌肺炎', '脓痰、肺脓肿、肺气囊', ul('金黄色葡萄球菌，多见于糖尿病、血液病患者', '**脓性痰**或脓血痰', 'X 线：**肺气囊**、多发脓肿，阴影易变', '耐甲氧西林者用 **万古霉素**')],
  ['克雷伯杆菌肺炎', '砖红色胶冻样痰', ul('多见于老年、酗酒、慢性病人群', '**砖红色胶冻状痰**', 'X 线：叶间裂下坠', '首选第三代头孢菌素')],
  ['支原体肺炎', '青少年、刺激性干咳', ul('多发于**青少年**，秋冬季', '**刺激性干咳**，症状重于体征', '冷凝集试验阳性，血清支原体 IgM 阳性', '首选 **大环内酯类**（如阿奇霉素）')],
  ['军团菌肺炎', '空调、水源、相对缓脉', ul('嗜肺军团菌，经**空调冷却水**传播', '高热、**相对缓脉**、意识改变', '低钠血症、肝功能异常', '首选 **红霉素/阿奇霉素/左氧氟沙星**')],
  ['社区获得性肺炎的诊断', '症状加影像', ul('**新出现**咳嗽、咳痰或原有症状加重，伴脓痰', '发热', '肺实变体征和（或）湿性啰音', '白细胞 > 10×10⁹/L 或 < 4×10⁹/L', '影像学检查显示片状、斑片状浸润性阴影或间质改变')],
  ['重症肺炎的判断标准', '主要标准与次要标准', ul('主要标准：**需要气管插管机械通气**；**感染性休克**需血管活性药物', '次要标准：呼吸频率 ≥ 30 次/分、PaO₂/FiO₂ ≤ 250、多肺叶浸润、意识障碍、BUN ≥ 7 mmol/L、低血压需液体复苏', '符合 1 项主要标准或 ≥ 3 项次要标准')],
  ['肺炎的抗生素治疗原则', '早期经验性、后期针对性', ul('确诊后尽早使用抗生素，**72 小时**后评估疗效', '青壮年无基础疾病：青霉素类、大环内酯类', '老年或有基础疾病：二代头孢、呼吸喹诺酮', '疗程至体温正常后 **3 天**，一般 5~7 天')],
])

part('内科学', '消化系统', '消化性溃疡', [
  ['胃溃疡与十二指肠溃疡鉴别', '疼痛节律与癌变', table(['项目', '胃溃疡', '十二指肠溃疡'], [['好发部位', '胃**小弯**、胃角', '十二指肠**球部**'], ['疼痛规律', '进食后 0.5~1 h 痛', '**空腹痛**、夜间痛，进食缓解'], ['胃酸分泌', '正常或偏低', '增高'], ['癌变', '**可癌变**', '极少癌变']])],
  ['幽门螺杆菌的检测与根除', '四联疗法', ul('检测：**¹³C/¹⁴C 尿素呼气试验**为首选的非侵入性方法', '根除：**PPI + 铋剂 + 两种抗生素**，疗程 14 天', '常用抗生素：阿莫西林、克拉霉素、甲硝唑、四环素', '停药 **4 周**后复查')],
  ['消化性溃疡的并发症', '出血、穿孔、幽门梗阻、癌变', ul('**出血**：最常见，DU 多于 GU', '**穿孔**：突发剧烈腹痛，X 线膈下游离气体', '**幽门梗阻**：呕吐宿食，振水音', '**癌变**：GU 多见，大便潜血持续阳性')],
  ['消化性溃疡的药物治疗', '抑酸、保护黏膜、根除 Hp', ul('**PPI**：抑酸首选，奥美拉唑', 'H₂ 受体拮抗剂：雷尼替丁', '黏膜保护剂：硫糖铝、**铋剂**、米索前列醇', 'GU 疗程 6~8 周，DU 疗程 4~6 周')],
  ['上消化道出血的病因', '消化性溃疡最常见', ul('**消化性溃疡**最常见', '食管胃底静脉曲张破裂', '急性糜烂出血性胃炎', '胃癌、胆道出血', '呕血 > 250~300 ml，黑便提示出血量 > 50~100 ml')],
  ['卓-艾综合征', '胃泌素瘤', ul('**胃泌素瘤**导致高胃泌素血症', '难治性、多发、不典型部位的溃疡', '基础胃酸分泌量 > 15 mmol/h', '血清胃泌素 > 200 pg/ml 并存在高胃酸分泌')],
  ['慢性胃炎的分类', 'A 型与 B 型', table(['项目', 'A 型', 'B 型'], [['病变部位', '胃体、胃底', '胃窦'], ['病因', '**自身免疫**', '**幽门螺杆菌**感染'], ['抗体', '抗壁细胞抗体、抗内因子抗体', '无'], ['并发症', '恶性贫血', '胃癌']])],
  ['溃疡穿孔的诊断与处理', '腹膜刺激征、膈下游离气体', ul('突发上腹剧痛，迅速蔓延全腹，**板状腹**', 'X 线立位平片：**膈下游离气体**', '禁食、胃肠减压、抗感染', '穿孔 6~8 h 内可行手术修补')],
])

part('生理学', '血液循环', '心脏生理', [
  ['心肌细胞动作电位的分期', '0、1、2、3、4 期', table(['时期', '主要离子', '名称'], [['0 期', 'Na⁺内流', '快速去极化'], ['1 期', 'K⁺外流', '快速复极初期'], ['2 期', 'Ca²⁺内流与 K⁺外流平衡', '**平台期**'], ['3 期', 'K⁺外流', '快速复极末期'], ['4 期', 'Na⁺-K⁺泵', '静息期']])],
  ['心输出量及其影响因素', '前负荷、后负荷、心肌收缩力、心率', ul('心输出量 = **搏出量 × 心率**', '前负荷：心室舒张末期容积，遵循 **Frank-Starling 定律**', '后负荷：大动脉血压', '心肌收缩力：与肌钙蛋白、Ca²⁺ 有关')],
  ['窦房结为何是正常起搏点', '4 期自动去极化速度最快', ul('窦房结 P 细胞 **4 期自动去极化速度最快**', '浦肯野细胞自律性最低', '**抢先占领**与**超速驱动压抑**', '其他自律组织为潜在起搏点')],
  ['心脏的传导顺序与速度', '房室延搁', ul('窦房结 → 心房肌 → 房室交界 → 房室束 → 浦肯野纤维 → 心室肌', '传导最慢：**房室交界**（房室延搁）', '传导最快：**浦肯野纤维**', '房室延搁保证心房收缩完成后心室才收缩')],
  ['心室肌有效不应期长的意义', '不会发生强直收缩', ul('有效不应期：从 0 期到 3 期复极至 **-60 mV**', '有效不应期长，一直延续到舒张早期', '意义：**不会产生强直收缩**，保证收缩与舒张交替', '期前收缩后常出现代偿间歇')],
  ['动脉血压的形成与影响因素', '心脏射血与外周阻力', ul('形成前提：**心血管系统有足够的血液充盈**', '收缩压主要反映**搏出量**', '舒张压主要反映**外周阻力**', '大动脉弹性贮器作用缓冲脉压')],
  ['心室的泵血过程', '等容收缩期、射血期、等容舒张期、充盈期', ul('等容收缩期：房室瓣关闭，动脉瓣尚未开放，**室内压升高最快**', '快速射血期：射出血量占总射血量 **2/3**', '等容舒张期：室内压下降最快', '快速充盈期：充盈量约占总充盈量 **2/3**')],
  ['心音的产生机制', '第一心音与第二心音', table(['心音', '标志', '机制'], [['第一心音', '心室收缩开始', '房室瓣关闭，音调低、持续长'], ['第二心音', '心室舒张开始', '半月瓣关闭，音调高、持续短']])],
])

const marks = new Map<number, { state: ProgressState; starred: boolean }>()
const seedMark = (id: number, state: ProgressState, starred: boolean) => marks.set(id, { state, starred })
seedMark(1, 'again', true)
seedMark(2, 'again', false)
seedMark(9, 'mastered', false)
seedMark(17, 'again', true)

export const cards = (): Card[] => cardDb.map((c) => ({ ...c, ...(marks.get(c.id) ?? {}) }))
const toIds = (v: unknown): number[] =>
  (Array.isArray(v) ? v.map(String) : String(v ?? '').split(',')).map(Number).filter((n) => Number.isFinite(n) && n > 0)
const on = (v: unknown) => v === true || v === 'true' || v === '1' || v === 1

registerMock('GET', '/cards/index', () => {
  const m = new Map<string, CardPartIndex>()
  for (const c of cardDb) {
    const k = `${c.subject}/${c.part}`
    const e = m.get(k)
    if (e) e.count++
    else m.set(k, { subject: c.subject, part: c.part, count: 1 })
  }
  return [...m.values()]
})

registerMock('GET', '/cards', ({ query }) => {
  const q = query as Record<string, unknown> & CardQuery
  let list = cards()
  const ids = toIds(q.ids)
  if (ids.length) list = ids.map((i) => list.find((c) => c.id === i)).filter((c): c is Card => !!c)
  else if (on(q.starred)) list = list.filter((c) => c.starred)
  else if (on(q.due)) list = list.filter((c) => c.state === 'again' || c.state === 'plan')
  else if (Number(q.plan_day) > 0) list = list.filter((c) => c.part === '循环系统' || c.part === '血液循环').slice(0, 10)
  else {
    if (q.subject) list = list.filter((c) => c.subject === q.subject)
    if (q.part) list = list.filter((c) => c.part === q.part)
  }
  return list
})

registerMock('GET', '/admin/cards/{id}', ({ params }) => {
  const c = cardDb.find((x) => x.id === Number(params.id))
  if (!c) throw new Error('卡片不存在')
  return { id: c.id, subject: c.subject, part: c.part, section: c.section, term: c.term, hint: c.hint, body: c.body_html.replace(/<[^>]+>/g, '') }
})
registerMock('PUT', '/admin/cards/{id}', ({ params, body }) => {
  const c = cardDb.find((x) => x.id === Number(params.id))
  if (!c) throw new Error('卡片不存在')
  const p = body as { section?: string; term?: string; hint?: string; body?: string }
  let changed = 0
  for (const key of ['section', 'term', 'hint'] as const) {
    if (p[key] !== undefined && p[key] !== c[key]) { c[key] = p[key]!; changed++ }
  }
  if (p.term !== undefined) c.term_html = p.term.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">')
  if (typeof p.body === 'string' && p.body !== c.body_html) { c.body_html = fmt(p.body); changed++ }
  return { changed }
})

const STATE_OF: Partial<Record<MarkAction, ProgressState>> = { rate_again: 'again', rate_good: 'mastered', plan: 'plan', master: 'mastered', wrong: 'again', unmaster: '', unwrong: '' }
registerMock('POST', '/progress/mark', ({ body }) => {
  const b = body as { target_type: string; target_id: number; action: MarkAction }
  if (b.target_type !== 'card') return NEXT
  const cur = marks.get(b.target_id) ?? { state: '' as ProgressState, starred: false }
  if (b.action === 'star') cur.starred = true
  else if (b.action === 'unstar') cur.starred = false
  else if (b.action in STATE_OF) cur.state = STATE_OF[b.action] ?? ''
  marks.set(b.target_id, cur)
  return undefined
})
