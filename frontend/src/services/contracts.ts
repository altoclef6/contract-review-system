import { api } from '../api'

export interface ContractVersion {
  id: string
  version_no: number
  file_name: string
  change_note?: string | null
  review_id?: string | null
  created_at: string
  created_by: string
  file_hash?: string | null
  version_type: 'original' | 'modified' | 're_review' | 'final'
  content_type?: string | null
  file_size?: number | null
  parse_status: 'pending' | 'ready' | 'failed' | 'unavailable'
  review_status?: string | null
  risk_level?: string | null
}

export interface ContractRecord {
  id: string
  title: string
  category: string
  tags: string[]
  counterparty?: string | null
  amount?: string | number | null
  currency?: string | null
  file_name?: string | null
  description?: string | null
  status: string
  is_favorite: boolean
  created_at: string
  updated_at: string
  created_by: string
  owner_name?: string | null
  updated_by: string
  versions: ContractVersion[]
  current_version: number
  latest_risk_level?: string | null
  risk_count?: number | null
}

export interface ReviewSummary {
  review_id: string
  created_at: string
  status: string
  risk_level?: string | null
  risk_count?: number | null
  duration_ms?: number | null
  report_available: boolean
}

export interface ContractDetail {
  contract: ContractRecord
  recent_reviews: ReviewSummary[]
  reports: ReviewSummary[]
  audit_logs: Array<{
    action: string
    actor_id?: string | null
    created_at: string
    metadata: Record<string, unknown>
  }>
}

export interface ContractListParams {
  page: number
  page_size: number
  search?: string
  category?: string
  status?: string
  risk_level?: string
  sort_by?: string
  sort_order?: string
  include_deleted?: boolean
}

export async function fetchContracts(params: ContractListParams, signal?: AbortSignal) {
  const response = await api.get('/contracts', { params, signal })
  return response.data.data as { items: ContractRecord[]; total: number; page: number; page_size: number }
}

export async function fetchContractOverview(contractId: string, signal?: AbortSignal) {
  const response = await api.get(`/contracts/${contractId}/overview`, { signal })
  return response.data.data as ContractDetail
}

export async function createContract(payload: Record<string, unknown>) {
  const response = await api.post('/contracts', payload)
  return response.data.data as ContractRecord
}

export async function uploadContractVersion(contractId: string, file: File, changeNote?: string) {
  const form = new FormData()
  form.append('contract_file', file)
  form.append('version_type', 'modified')
  if (changeNote) form.append('change_note', changeNote)
  const response = await api.post(`/contracts/${contractId}/versions/upload`, form)
  return response.data.data as ContractVersion
}

export async function archiveContract(contractId: string) {
  return (await api.post(`/contracts/${contractId}/archive`)).data.data as ContractRecord
}

export async function restoreContract(contractId: string) {
  return (await api.post(`/contracts/${contractId}/restore`)).data.data as ContractRecord
}

export async function deleteContract(contractId: string) {
  return (await api.delete(`/contracts/${contractId}`)).data.data as ContractRecord
}

export async function startContractReview(contractId: string, versionId: string) {
  return (await api.post(`/contracts/${contractId}/versions/${versionId}/review`)).data.data as {
    task_id: string
    status: string
    result_summary: { review_id?: string; risk_count?: number }
  }
}

async function downloadBlob(url: string, fallbackName: string) {
  const response = await api.get(url, { responseType: 'blob' })
  const objectUrl = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

export function downloadContractVersion(contractId: string, version: ContractVersion) {
  return downloadBlob(`/contracts/${contractId}/versions/${version.id}/download`, version.file_name)
}

export function downloadReviewReport(reviewId: string) {
  return downloadBlob(`/reviews/${reviewId}/download?file_type=pdf`, `${reviewId}.pdf`)
}
