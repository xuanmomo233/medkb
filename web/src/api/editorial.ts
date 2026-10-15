import { get, put } from './client'

export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'needs_revision'
export type ReviewQueue = 'needs_review' | 'waiting_execution' | 'completed' | 'all'
export interface ReviewDecision {
  status: ReviewStatus
  note: string
  version: number
  updated_by: number | null
  updated_at: string | null
}
export interface ReviewExecution {
  status: string
  description: string
  affected_ids: number[]
  batch_id: string
  created_at: string
  needs_recheck: boolean
}
export interface ReviewSummary {
  id: string
  category: string
  title: string
  subjects: string[]
  card_ids: number[]
  decision: ReviewDecision
  work_queue: Exclude<ReviewQueue, 'all'>
  execution?: ReviewExecution | null
}
export interface ReviewList {
  dataset_id: string
  audit_date: string
  counts: Record<string, number>
  queue_counts: Record<ReviewQueue, number>
  total: number
  offset: number
  items: ReviewSummary[]
}
interface ReviewCard {
  id: number
  subject: string
  part: string
  section: string
  term: string
  term_html: string
  hint: string
  body: string
  body_html: string
  source_file: string
}
export interface ReviewDetail extends ReviewSummary {
  dataset_id: string
  audit_date: string
  guidance: string
  evidence: string
  proposal_html: string
  original_html?: string
  chapter_id?: number
  source_file?: string
  line?: number
  executed: boolean
  differing_fields: string[]
  requires_media_review: boolean
  sources: { title: string; url: string }[]
  cards: { snapshot: ReviewCard; current: ReviewCard | null; changed: boolean; merged_into?: number | null }[]
}

export const reviewApi = {
  list: (q: { category: string; status: string; q: string; offset: number; queue: ReviewQueue }) => get<ReviewList>('/admin/reviews', q),
  detail: (id: string) => get<ReviewDetail>(`/admin/reviews/${encodeURIComponent(id)}`),
  save: (id: string, body: { status: ReviewStatus; note: string; expected_version: number }) =>
    put<ReviewDecision>(`/admin/reviews/${encodeURIComponent(id)}/decision`, body),
}
