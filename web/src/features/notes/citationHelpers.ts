import type { ContentCitation, ContentCitationInput } from '@/api/types'

export const citationInputs = (items: ContentCitation[] = []): ContentCitationInput[] => items.map((citation) => ({
  source_key: citation.source_key, chapter: citation.chapter, section: citation.section,
  page_start: citation.page_start, page_end: citation.page_end, note: citation.note, status: citation.status,
}))

export const sameCitations = (left: ContentCitationInput[], right: ContentCitationInput[]) =>
  JSON.stringify(left) === JSON.stringify(right)
