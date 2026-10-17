import { del, get, post, put } from './client'
import type * as T from './types'

export const api = {
  // 账号
  register: (b: { username: string; password: string; invite_code: string }) => post<T.AuthResult>('/auth/register', b),
  changePassword: (b: { old_password: string; new_password: string }) => put<void>('/auth/password', b),
  login: (b: { username: string; password: string }) => post<T.AuthResult>('/auth/login', b),
  logout: () => post<void>('/auth/logout'),
  me: () => get<T.User>('/auth/me'),
  version: () => get<T.VersionInfo>('/version'),

  // 内容
  tree: () => get<T.ContentTree>('/content/tree'),
  textbooks: () => get<{ sources: T.TextbookSource[] }>('/content/textbooks'),
  chapter: (id: number) => get<T.ChapterDetail>(`/content/chapters/${id}`),
  search: (q: string, kind?: T.SearchKind) => get<T.SearchHit[]>('/search', { q, kind }),

  // 背卡
  cardIndex: () => get<T.CardPartIndex[]>('/cards/index'),
  cards: (q: T.CardQuery) => get<T.Card[]>('/cards', { ...q }),

  // 刷题
  facets: (f: T.QuizFilter) => get<T.FacetProgress>('/quiz/facets', { ...f }),
  questions: (q: T.QuizQuery & { lite?: boolean }) => get<T.Question[]>('/quiz/questions', { ...q }),
  questionFull: (id: number) => get<T.QuestionFull>(`/quiz/questions/${id}`),
  cardSources: (id: number) => get<T.Question[]>(`/cards/${id}/sources`),
  relatedQuestions: (id: number) => get<T.RelatedQuestion[]>(`/quiz/questions/${id}/related`),
  aiAnalysis: (id: number) => post<{ analysis_html: string }>(`/quiz/questions/${id}/ai-analysis`),
  attempt: (b: { question_id: number; picked: number[] }) => post<T.AttemptResult>('/quiz/attempts', b),
  submitExam: (b: { title: string; items: T.SubmitItem[] }) => post<T.ExamReport>('/quiz/submit', b),
  mock: (n = 180) => get<{ ids: number[] }>('/quiz/mock', { n }),
  pool: (q: T.QuizFilter & { flt?: T.PoolFilter; offset?: number; size?: number }) => get<T.PoolPage>('/quiz/pool', { ...q }),
  wrongbook: () => get<T.WrongBookGroup[]>('/quiz/wrongbook'),
  exams: () => get<T.ExamRecord[]>('/quiz/exams'),

  // 进度
  mark: (b: { target_type: T.TargetType; target_id: number; action: T.MarkAction }) => post<void>('/progress/mark', b),

  // 今日 / 计划 / 统计
  today: () => get<T.TodaySummary>('/today'),
  checkin: () => post<{ streak: number }>('/checkin'),
  calendar: (month: string) => get<T.CalendarMonth>('/calendar', { month }),
  prefs: () => get<T.UserPrefs>('/prefs'),
  savePrefs: (p: Partial<T.UserPrefs>) => put<T.UserPrefs>('/prefs', p),
  plan: () => get<T.PlanToday>('/plan'),
  planDay: (n: number) => get<T.PlanDayDetail>(`/plan/days/${n}`),
  planRestart: () => post<void>('/plan/restart'),
  planOptions: () => get<T.PlanOption[]>('/plan/options'),
  planSaveConfig: (b: { total_days: number; items: { subject: string; part: string }[] }) => put<void>('/plan/config', b),
  planClear: () => del<void>('/plan/config'),
  statsOverview: () => get<T.StatsOverview>('/stats/overview'),
  weakSpots: () => get<T.WeakSpot[]>('/stats/weakspots'),
  scheduleToday: () => get<T.ScheduleToday>('/schedule/today'),
  scheduleDone: (id: number) => post<void>(`/schedule/items/${id}/done`),

  // 笔记
  notesOf: (target_type: T.TargetType, target_id: number) => get<T.Note[]>('/notes', { target_type, target_id }),
  notesMine: () => get<T.Note[]>('/notes/mine'),
  noteAdd: (b: { target_type: T.TargetType; target_id: number; body: string; is_public: boolean }) => post<void>('/notes', b),
  noteDelete: (id: number) => del<void>(`/notes/${id}`),
  publicNotes: (target_type: T.TargetType, target_id: number) => get<T.PublicNote[]>('/notes/public', { target_type, target_id }),
  noteLike: (id: number) => post<{ likes: number; liked: boolean }>(`/notes/${id}/like`),

  // AI 陪学
  chatHistory: () => get<T.ChatMessage[]>('/chat/history'),
  chatSend: (b: T.ChatSendBody) => post<T.ChatReply>('/chat/messages', b),
  chatAnswer: (b: { qid: string; answer: string }) => post<T.ChatAnswerResult>('/chat/answer', b),
  chatClear: () => del<void>('/chat/history'),

  // 管理员
  adminPreview: (b: { text: string; kind: 'markdown' | 'card' }) => post<{ html: string }>('/admin/preview', b),
  adminQuestion: (id: number) => get<T.AdminQuestion>(`/admin/questions/${id}`),
  adminSaveQuestion: (id: number, p: T.AdminQuestionPatch) => put<{ changed: number }>(`/admin/questions/${id}`, p),
  adminCard: (id: number) => get<T.AdminCard>(`/admin/cards/${id}`),
  adminSaveCard: (id: number, p: T.AdminCardPatch) => put<{ changed: number }>(`/admin/cards/${id}`, p),
  adminSaveCitations: (type: 'chapter' | 'question' | 'card', id: number, citations: T.ContentCitationInput[]) =>
    put<T.ContentCitation[]>(`/admin/content/${type}/${id}/citations`, { citations }),
  adminInvites: () => get<T.Invite[]>('/admin/invites'),
  adminNewInvite: (count = 1) => post<T.Invite[]>('/admin/invites', { count }),
  adminRevokeInvite: (code: string) => del(`/admin/invites/${code}`),
  adminSite: () => get<T.SiteConfig>('/admin/site'),
  adminSaveSite: (b: { exam_date: string | null }) => put<T.SiteConfig>('/admin/site', b),
  adminUsers: (q?: { q?: string; invite?: string }) => get<T.AdminUser[]>('/admin/users', q ?? {}),
  adminDeleteUser: (id: number, password: string) => del<void>(`/admin/users/${id}`, undefined, { password }),
}
