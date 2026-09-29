import type { AgentEvent, CompanyProfile, Report } from './types'

// Fictional companies and people. Shaped exactly like a real API response so the demo
// exercises the same UI code path as a live analysis. Registry fields stay in Portuguese,
// as Receita Federal publishes them.

export const DEMO_CNPJ = '99.888.777/0001-00'
export const DEMO_PURPOSE = 'Hire a company for the electrical refurbishment of an industrial warehouse'

const HOLDING: CompanyProfile = {
  cnpj: '44555666000181',
  legal_name: 'HOLDING EXEMPLO PARTICIPACOES LTDA',
  status: 'ATIVA',
  opened_on: '2008-01-10',
  legal_nature: 'Sociedade Empresária Limitada',
  share_capital: 2_000_000,
  main_activity_code: 6462000,
  main_activity: 'Holdings de instituições não-financeiras',
  secondary_activities: [],
  city: 'BARREIRAS',
  state: 'BA',
  partners: [{ name: 'JOAO EXEMPLO', role: 'Sócio-Administrador', document: '***123456**' }],
}

const REPORT: Report = {
  company: {
    cnpj: '99888777000100',
    legal_name: 'SERVICOS NOVOS LTDA',
    status: 'ATIVA',
    opened_on: '2026-06-01',
    legal_nature: 'Sociedade Empresária Limitada',
    size: 'MICRO EMPRESA',
    share_capital: 100,
    main_activity_code: 8211300,
    main_activity: 'Serviços combinados de escritório e apoio administrativo',
    secondary_activities: ['4321500 - Instalação e manutenção elétrica'],
    city: 'BARREIRAS',
    state: 'BA',
    partners: [
      {
        name: 'HOLDING EXEMPLO PARTICIPACOES LTDA',
        role: 'Sócio',
        document: '44555666000181',
        since: '2026-06-01',
      },
    ],
  },
  sanctions: { checked: true, sanctions: [] },
  risk: {
    score: 20,
    level: 'MEDIUM',
    complete: true,
    signals: [
      {
        code: 'VERY_NEW_COMPANY',
        severity: 'medium',
        points: 15,
        message: 'Company is less than 1 year old (opened 2026-06-01).',
        source: 'Receita Federal (company registry)',
      },
      {
        code: 'LOW_SHARE_CAPITAL',
        severity: 'low',
        points: 5,
        message: 'Declared share capital is very low (BRL 100.00).',
        source: 'Receita Federal (company registry)',
      },
    ],
  },
  narrative: {
    summary:
      'Active company opened 4 months ago, with no federal sanctions on CEIS or CNEP. It is controlled by a holding company that has been active for 18 years and is in good standing. The risk comes from its short track record and token share capital, not from any irregularity.',
    activity_fit: 'partial',
    activity_fit_reason:
      'Its primary activity is office support services; electrical installation only appears as a secondary activity code (CNAE 4321500). It is allowed to do the job, but it is not its declared specialty.',
    attention_points: [
      'No track record: there are no previous projects verifiable in public sources.',
      'Share capital of BRL 100 offers almost no financial backing in case of damage or default.',
      'The parent company is healthy, which reduces the risk of the deal but does not remove it.',
    ],
    recommendations: [
      'Ask for technical capability certificates and the engineer-of-record registration (CREA/ART).',
      'Require federal tax, FGTS and labor clearance certificates before signing.',
      'Pay per completed milestone and require a performance bond in the contract.',
    ],
  },
  related_companies: [HOLDING],
  sources: [
    {
      name: 'Receita Federal (via BrasilAPI)',
      url: 'https://brasilapi.com.br/api/cnpj/v1/99888777000100',
      consulted_at: '2026-09-29T14:02:11+00:00',
    },
    {
      name: 'Portal da Transparência — CEIS',
      url: 'https://api.portaldatransparencia.gov.br/api-de-dados/ceis?codigoSancionado=99888777000100',
      consulted_at: '2026-09-29T14:02:11+00:00',
    },
    {
      name: 'Portal da Transparência — CNEP',
      url: 'https://api.portaldatransparencia.gov.br/api-de-dados/cnep?codigoSancionado=99888777000100',
      consulted_at: '2026-09-29T14:02:12+00:00',
    },
    {
      name: 'Receita Federal (via BrasilAPI)',
      url: 'https://brasilapi.com.br/api/cnpj/v1/44555666000181',
      consulted_at: '2026-09-29T14:02:15+00:00',
    },
  ],
  model: 'claude-opus-5-5',
  language: 'en',
}

const target = { cnpj: '99888777000100' }
const holding = { cnpj: '44555666000181' }

export const DEMO_EVENTS: AgentEvent[] = [
  { type: 'tool_call', tool: 'lookup_company', input: target },
  { type: 'tool_call', tool: 'check_sanctions', input: target },
  { type: 'tool_result', tool: 'lookup_company', input: target, ok: true },
  { type: 'tool_result', tool: 'check_sanctions', input: target, ok: true },
  { type: 'tool_call', tool: 'lookup_company', input: holding },
  { type: 'tool_call', tool: 'check_sanctions', input: holding },
  { type: 'tool_call', tool: 'assess_risk', input: target },
  { type: 'tool_result', tool: 'lookup_company', input: holding, ok: true },
  { type: 'tool_result', tool: 'check_sanctions', input: holding, ok: true },
  { type: 'tool_result', tool: 'assess_risk', input: target, ok: true },
  { type: 'report', report: REPORT },
]

export async function replayDemo(
  onEvent: (event: AgentEvent) => void,
  delayMs = 650,
  signal?: AbortSignal,
): Promise<void> {
  for (const event of DEMO_EVENTS) {
    if (signal?.aborted) return
    await new Promise((resolve) => setTimeout(resolve, event.type === 'report' ? delayMs * 2 : delayMs))
    onEvent(event)
  }
}
