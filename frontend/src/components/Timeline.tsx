import { maskCnpj } from '../cnpj'
import type { AgentEvent, ToolName } from '../types'
import { buildSteps } from './steps'

const LABELS: Record<ToolName, string> = {
  lookup_company: 'Company registry (Receita Federal)',
  check_sanctions: 'Debarment lists (CEIS / CNEP)',
  assess_risk: 'Risk rules',
}

interface Props {
  events: AgentEvent[]
  targetCnpj: string
  finished: boolean
}

export function Timeline({ events, targetCnpj, finished }: Props) {
  const steps = buildSteps(events)
  const target = targetCnpj.replace(/\D/g, '')

  return (
    <section className="timeline" aria-label="Agent steps">
      <h2 className="section-label">What the agent is doing</h2>
      <ol>
        {steps.map((step) => (
          <li key={step.key} className={`step step--${step.status}`}>
            <span className="step__icon" aria-hidden="true" />
            <span className="step__text">
              {LABELS[step.tool]}
              <span className="step__cnpj">
                {maskCnpj(step.cnpj)}
                {step.cnpj.replace(/\D/g, '') !== target && ' · shareholder company'}
              </span>
            </span>
            <span className="visually-hidden">
              {step.status === 'running' ? 'in progress' : step.status === 'ok' ? 'done' : 'failed'}
            </span>
          </li>
        ))}
        {!finished && (
          <li className="step step--thinking">
            <span className="step__icon" aria-hidden="true" />
            <span className="step__text">
              {steps.length === 0 ? 'Planning the investigation…' : 'Reasoning over the results…'}
            </span>
          </li>
        )}
      </ol>
    </section>
  )
}
