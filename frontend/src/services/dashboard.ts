import { api } from '../api'

export interface DashboardMetrics {
  monthly_review_count: number
  monthly_high_risk_contract_count: number
  pending_human_review_risk_count: number | null
  average_review_duration_ms: number | null
}

export interface DashboardTrendPoint { date: string; count: number }
export interface DashboardDistributionItem { key: string; label: string; value: number }
export interface DashboardRuleItem { rule_id: string; title: string; count: number }
export interface DashboardRecentTask {
  review_id: string
  contract_name: string
  contract_type: string
  status: string
  risk_level: string | null
  started_at: string | null
  duration_ms: number | null
}
export interface DashboardTodoItem {
  id: string
  source: string
  title: string
  description: string
  status: string
  updated_at: string
  action_path: string
}

export interface DashboardSummary {
  generated_at: string
  time_zone: string
  scope: 'all' | 'owned'
  metrics: DashboardMetrics
  review_trend_30d: DashboardTrendPoint[]
  risk_level_distribution: DashboardDistributionItem[]
  contract_type_distribution: DashboardDistributionItem[]
  top_risk_rules: DashboardRuleItem[] | null
  recent_tasks: DashboardRecentTask[]
  todos: DashboardTodoItem[]
  unavailable_reasons: Record<string, string>
  statistics_notes: string[]
}

export async function fetchDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  const response = await api.get('/dashboard/summary', { signal })
  return response.data.data
}
