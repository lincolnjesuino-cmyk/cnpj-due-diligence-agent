// Mirrors backend/app/models.py (Report and friends).

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type ActivityFit = 'compatible' | 'partial' | 'incompatible' | 'not_evaluated'

export interface Partner {
  name: string
  role?: string
  document?: string
  since?: string
}

export interface CompanyProfile {
  cnpj: string
  legal_name: string
  trade_name?: string
  status: string
  status_reason?: string
  opened_on?: string
  legal_nature?: string
  size?: string
  share_capital?: number
  main_activity_code?: number
  main_activity?: string
  secondary_activities: string[]
  city?: string
  state?: string
  partners: Partner[]
}

export interface Sanction {
  registry: string
  sanction_type?: string
  authority?: string
  start?: string
  end?: string
  link?: string
}

export interface SanctionsResult {
  checked: boolean
  sanctions: Sanction[]
  note?: string
}

export interface RiskSignal {
  code: string
  severity: Severity
  points: number
  message: string
  source: string
}

export interface RiskAssessment {
  score: number
  level: RiskLevel
  signals: RiskSignal[]
  complete: boolean
}

export interface Narrative {
  summary: string
  activity_fit: ActivityFit
  activity_fit_reason: string
  attention_points: string[]
  recommendations: string[]
}

export interface SourceRef {
  name: string
  url: string
  consulted_at: string
}

export interface Report {
  company: CompanyProfile
  sanctions: SanctionsResult
  risk: RiskAssessment
  narrative: Narrative
  related_companies: CompanyProfile[]
  sources: SourceRef[]
  model: string
  language: Language
}

export type ToolName = 'lookup_company' | 'check_sanctions' | 'assess_risk'
export type Language = 'en' | 'pt'

export type AgentEvent =
  | { type: 'tool_call'; tool: ToolName; input: { cnpj: string } }
  | { type: 'tool_result'; tool: ToolName; input: { cnpj: string }; ok: boolean }
  | { type: 'report'; report: Report }
  | { type: 'error'; message: string }
