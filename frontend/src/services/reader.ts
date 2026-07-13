import { api } from '../api'

export interface ReaderRiskLocation {
  status: string
  start_offset?: number | null
  end_offset?: number | null
  paragraph_index?: number | null
  page_number?: number | null
  bounding_box?: number[] | null
  is_ambiguous: boolean
}

export interface ReaderKnowledgeBasis {
  document_id: string
  name: string
  article_number?: string | null
  source_type: string
  status: string
  updated_at?: string | null
}

export interface ReaderRisk {
  risk_id: string
  source_risk_id?: string | null
  title: string
  category: string
  severity: string
  clause_text: string
  explanation: string
  recommendation: string
  suggested_revision?: string | null
  source: string
  rule_id?: string | null
  detection_method: string
  ai_involved: boolean
  confidence?: number | null
  location: ReaderRiskLocation
  knowledge_basis: ReaderKnowledgeBasis[]
  status: string
  revision: number
  persisted: boolean
  assignee_id?: string | null
  reviewer_id?: string | null
  review_comment?: string | null
  revised_clause?: string | null
}

export interface ReaderChapter {
  chapter_id: string
  title: string
  start_offset: number
  end_offset: number
  risk_count: number
  high_risk_count: number
}

export interface ReaderWorkspace {
  summary: {
    review_id: string
    contract_id?: string | null
    contract_version_id?: string | null
    contract_name: string
    contract_type: string
    contract_version?: number | null
    status: string
    reviewed_at: string
    operator_name?: string | null
    overall_risk_level?: string | null
    risk_score?: number | null
    risk_count: number
    report_available: boolean
    source_is_pdf: boolean
  }
  contract_text: string
  risks: ReaderRisk[]
  chapters: ReaderChapter[]
}

export async function fetchReaderWorkspace(reviewId: string, signal?: AbortSignal) {
  const response = await api.get(`/reader/${reviewId}/workspace`, { signal })
  return response.data.data as ReaderWorkspace
}

export async function locatePdfText(reviewId: string, text: string, signal?: AbortSignal) {
  const response = await api.get(`/reader/${reviewId}/locations`, {
    params: { text: text.slice(0, 300) },
    signal,
  })
  return response.data.data.locations as Array<{
    page: number
    x0: number
    y0: number
    x1: number
    y1: number
    text: string
  }>
}

export async function downloadReaderReport(reviewId: string) {
  const response = await api.get(`/reviews/${reviewId}/download?file_type=pdf`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${reviewId}.pdf`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
