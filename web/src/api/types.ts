// API v2 契约：前端（Web/Flutter）与 FastAPI 后端共同遵守。所有时间为 ISO 8601 字符串，日期为 YYYY-MM-DD。
// 服务端渲染的 HTML 字段（*_html）已做白名单消毒，前端仍需经 <HtmlView> 二次消毒后渲染。

export interface User { id: number; username: string; is_admin: boolean }
export interface AuthResult { token: string; user: User }

export type CitationStatus = 'unverified' | 'verified' | 'disputed'
export interface TextbookSource { key: string; title: string; subject: string; publisher: string; edition: string }
export interface ContentCitationInput {
  source_key: string
  chapter: string
  section: string
  page_start: number | null
  page_end: number | null
  note: string
  status: CitationStatus
}
export interface ContentCitation extends ContentCitationInput {
  id: number
  title: string
  subject: string
  publisher: string
  edition: string
  verified_by: number | null
  verified_at: string | null
}

// ---------- 内容 ----------
export interface ChapterBrief { id: number; subject: string; title: string }
export interface QuestionChapter { name: string; count: number }
export interface QuestionSystem { name: string; chapters: QuestionChapter[] }
export interface QuestionSubject { subject_dir: string; systems: QuestionSystem[] }
export interface ContentTree {
  mindmaps: ChapterBrief[]
  notes: ChapterBrief[]
  question_tree: QuestionSubject[]
}
export interface ChapterDetail {
  id: number
  title: string
  subject: string
  html: string
  meta: Record<string, string>
  pages: number[] // 导图页图：/img/page_{n}.webp
  citations?: ContentCitation[]
}
export type SearchKind = 'question' | 'card' | 'chapter'
export interface SearchHit {
  kind: SearchKind
  id: number
  title: string
  snippet: string
  state: ProgressState
  starred: boolean
}

// ---------- 进度 ----------
export type ProgressState = '' | 'again' | 'mastered' | 'plan'
export type TargetType = 'question' | 'card'
export type MarkAction =
  | 'star' | 'unstar' | 'plan' | 'unplan' | 'seen'
  | 'wrong' | 'unwrong' | 'master' | 'unmaster'
  | 'rate_again' | 'rate_hard' | 'rate_good'

// ---------- 背卡 ----------
export interface CardPartIndex { subject: string; part: string; count: number }
export interface Card {
  id: number
  subject: string
  part: string
  section: string
  term: string
  term_html: string
  hint: string
  body_html: string
  state: ProgressState
  starred: boolean
  related_cards?: { id: number; term: string; subject: string; part: string; reason: string }[]
  citations?: ContentCitation[]
}
export interface CardQuery {
  subject?: string; part?: string; ids?: number[]
  plan_day?: number; starred?: boolean; due?: boolean
}

// ---------- 刷题 ----------
export type QuizMode = 'practice' | 'recite' | 'quick' | 'test'
export interface QuizFilter {
  bank_group?: string; bank?: string; subject_dir?: string
  system?: string; chapter?: string; qtype?: string
}
export type FacetLevel = 'bank_group' | 'bank' | 'subject_dir' | 'system' | 'chapter' | 'qtype'
/** 每级选项 → [总数, 已做数] */
export type FacetProgress = Record<FacetLevel, Record<string, [number, number]>>

export interface QuizQuery extends QuizFilter {
  ids?: number[]; plan_day?: number
  starred?: boolean; wrong?: boolean; due?: boolean
  random?: boolean; shuffle?: boolean; fresh?: boolean; limit?: number
}
export interface Question {
  id: number
  qid: string
  chapter: string
  system: string
  qtype: string
  stem_html: string
  parent_html: string
  case_group?: string
  case_index?: number
  case_total?: number
  options_html: string[]
  option_labels?: string[] // 缺失或空列表为旧接口，按连续 A、B… 回退
  answer: string // 如 "A" / "ABD"；主观题可能非字母
  analysis_html: string // 懒加载模式下可能为空，用 getQuestionFull 取
  analysis_empty: boolean
  tags: string[]
  state: ProgressState
  starred: boolean
  done: boolean
  last_picked: string // 上次作答选项字母，没做过为 ''
  last_correct: boolean | null
}
export interface QuestionStat { total: number; correct: number; dist: Record<string, number> }
export interface RelatedCard { id: number; term: string; term_html: string; hint: string; body_html: string }
export interface RelatedQuestion {
  id: number; qid: string; chapter: string; qtype: string; stem: string
  kind: 'variant' | 'same_concept' | 'contrast'; label: string; reason: string; in_plan: boolean
}
export interface QuestionFull {
  id: number
  system: string
  stem_html: string
  options_html?: string[]
  option_labels?: string[]
  answer: string
  analysis_html: string
  analysis_empty: boolean
  related_cards: RelatedCard[]
  stat: QuestionStat
  tags: string[]
  state: ProgressState
  starred: boolean
  citations?: ContentCitation[]
}
export interface AttemptResult { correct: boolean | null; answer: string; stat: QuestionStat }
export interface SubmitItem { question_id: number; picked: number[] }
export interface ExamReport {
  total: number; correct: number
  score_100: number; score_300: number
  wrong_ids: number[]
  by_chapter: { chapter: string; total: number; correct: number; rate: number }[]
  results: { question_id: number; judged: boolean; correct?: boolean; answer: string }[]
}
export type PoolFilter = 'done' | 'todo' | 'wrong' | 'starred' | 'plan' | 'mastered'
export interface PoolItem {
  id: number; qid: string; stem: string; answer: string; source: string; tags: string[]
  state: ProgressState; starred: boolean; in_plan: boolean; done: boolean
  attempts: number; wrong_count: number; last_wrong_at: string | null
}
export interface PoolPage {
  stats: { total: number; done: number; wrong: number; starred: number; plan: number; mastered: number }
  items: PoolItem[]
}
export interface WrongBookGroup { chapter: string; count: number; wrong_total: number; last_wrong_at: string | null }
export interface ExamRecord { id: number; created_at: string; title: string; total: number; correct: number; rate: number }

// ---------- 今日 / 计划 / 统计 ----------
export interface UserPrefs {
  daily_goal: number
  exam_date: string | null
  weak_min_samples: number // 薄弱点最少样本数（用户可设）
  weak_max_rate: number // 薄弱点正确率上限 0~1（用户可设）
}
export interface TodaySummary {
  streak: number
  checked_in: boolean
  daily_goal: number
  done_today: number
  exam_days_left: number | null
  exam_date: string | null
  counts: { due: number; wrong: number; starred: number; mastered: number }
}
export interface CalendarMonth { days: number[]; streak: number }
export interface PlanItem {
  key: string; subject: string; part: string; label: string
  cards: number; card_done: number; questions: number; question_done: number
  done: boolean; day: number | null
}
export interface PlanToday {
  configured: boolean
  start: string | null; total_days: number; day_no: number; days_left: number
  remaining: number; finished: boolean
  today_questions: number; today_cards: number
  pending_questions: number; pending_cards: number; scheduled_days: number[]
  today_items: PlanItem[]; items: PlanItem[]
}
export interface PlanOptionPart { part: string; cards: number; questions: number }
export interface PlanOption { subject: string; parts: PlanOptionPart[] }
export interface PlanDayDetail {
  no: number; title: string
  cards: { id: number; term: string; part: string }[]
  question_groups: { chapter: string; ids: number[] }[]
}
export interface WeakSpot {
  system: string; chapter: string
  total: number; correct: number; rate: number
  last_attempt_at: string | null
}
export interface ScheduleItem {
  id: number
  item_type: TargetType
  item_id: number
  reason: 'due' | 'weak'
  title: string
  done: boolean
}
export interface ScheduleToday {
  day: string
  goal: number
  items: ScheduleItem[]
  done_count: number
}
export interface StatsOverview {
  total_questions: number; total_cards: number; total_chapters: number
  attempted: number; accuracy: number
  by_system: { system: string; total: number; correct: number; rate: number }[]
  daily: { day: string; count: number; correct: number }[] // 最近 30 天
}

// ---------- 笔记 / 评论 ----------
export interface Note {
  id: number; target_type: TargetType; target_id: number
  body: string; is_public: boolean; created_at: string
  stem_preview?: string
}
export interface PublicNote {
  id: number; body: string; created_at: string; username: string
  likes: number; liked: boolean; mine: boolean
}

// ---------- AI 陪学 ----------
export interface ChatQuizOption { key: string; html: string }
export interface ChatQuiz {
  qid: string; system: string; multi: boolean
  stem_html: string; options: ChatQuizOption[]
}
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  html: string
  created_at: string
}
export interface ChatReply { reply: string; reply_html: string; quizzes: ChatQuiz[] }
export interface ChatAnswerResult {
  correct: boolean; answer: string; qid: string; reply: string; reply_html: string
}
export interface ChatSendBody {
  message: string
  context?: string
  image?: string // dataURL
  file?: { name: string; data: string } // base64
}

// ---------- 管理员 ----------
export interface Invite { code: string; created_by: number; used_by: number | null; used_by_username: string | null; used_at: string | null; created_at: string | null }
export interface AdminUser { id: number; username: string; is_admin: boolean; created_at: string | null; last_login_at: string | null; invite_code: string | null }
export interface SiteConfig { exam_date: string }

export interface AdminQuestion { id: number; subject_dir: string; system: string; stem: string; options: string[]; option_labels?: string[]; answer: string; analysis: string; tags: string[]; citations?: ContentCitation[] }
export interface AdminQuestionPatch { system?: string; stem?: string; options?: string[]; option_labels?: string[]; answer?: string; analysis?: string; tags?: string[]; citations?: ContentCitationInput[] }
export interface AdminCard { id: number; subject: string; part: string; section: string; term: string; hint: string; body: string; citations?: ContentCitation[] }
export interface AdminCardPatch { section?: string; term?: string; hint?: string; body?: string; citations?: ContentCitationInput[] }
export interface VersionInfo { build: number; note: string }
