import { api } from '../api'

export type RiskStatus = 'pending_review' | 'confirmed' | 'rejected' | 'remediating' | 'remediated' | 'closed'

export interface RiskComment { comment_id: string; author_id: string; content: string; created_at: string }
export interface RiskStateEvent { event_id: string; actor_id: string; old_status?: RiskStatus | null; new_status: RiskStatus; reason?: string | null; created_at: string }
export interface RiskRecord {
  risk_id: string
  source_risk_id?: string | null
  contract_id?: string | null
  contract_version_id?: string | null
  review_id: string
  severity: string
  category: string
  title: string
  matched_text: string
  start_offset?: number | null
  end_offset?: number | null
  page_number?: number | null
  paragraph_index?: number | null
  rule_id?: string | null
  knowledge_document_ids: string[]
  legal_basis: Array<Record<string, unknown>>
  detection_source: string
  ai_involved: boolean
  confidence?: number | null
  risk_score: number
  explanation: string
  recommendation: string
  status: RiskStatus
  assignee_id?: string | null
  reviewer_id?: string | null
  review_comment?: string | null
  revised_clause?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
  confirmed_at?: string | null
  resolved_at?: string | null
  revision: number
  state_history: RiskStateEvent[]
  comments: RiskComment[]
  contract_title?: string | null
  contract_type?: string | null
  contract_version?: number | null
  assignee_name?: string | null
}

export interface RiskQuery {
  page: number; page_size: number; keyword?: string; severity?: string; category?: string
  status?: RiskStatus | ''; assignee_id?: string; contract_type?: string
  date_from?: string; date_to?: string; review_id?: string
}

export async function fetchRisks(params: RiskQuery, signal?: AbortSignal) {
  const response = await api.get('/risks', { params, signal })
  return response.data.data as { items: RiskRecord[]; total: number; page: number; page_size: number }
}

export async function fetchRisk(riskId: string, signal?: AbortSignal) {
  const response = await api.get(`/risks/${riskId}`, { signal })
  return response.data.data as RiskRecord
}

export async function transitionRisk(risk: RiskRecord, action: 'confirm' | 'reject' | 'start-remediation' | 'mark-remediated' | 'close', reason?: string) {
  const response = await api.post(`/risks/${risk.risk_id}/${action}`, { expected_revision: risk.revision, reason: reason || null })
  return response.data.data as RiskRecord
}

export async function assignRisk(risk: RiskRecord, assigneeId?: string | null) {
  const response = await api.post(`/risks/${risk.risk_id}/assign`, { expected_revision: risk.revision, assignee_id: assigneeId || null })
  return response.data.data as RiskRecord
}

export async function addRiskComment(risk: RiskRecord, content: string) {
  const response = await api.post(`/risks/${risk.risk_id}/comments`, { expected_revision: risk.revision, content })
  return response.data.data as RiskRecord
}

export async function saveRiskRevision(risk: RiskRecord, revisedClause: string) {
  const response = await api.put(`/risks/${risk.risk_id}/revised-clause`, { expected_revision: risk.revision, revised_clause: revisedClause })
  return response.data.data as RiskRecord
}
