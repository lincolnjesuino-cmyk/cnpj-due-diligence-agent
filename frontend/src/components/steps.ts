import type { AgentEvent, ToolName } from '../types'

export type StepStatus = 'running' | 'ok' | 'error'

export interface Step {
  key: string
  tool: ToolName
  cnpj: string
  status: StepStatus
}

export function buildSteps(events: AgentEvent[]): Step[] {
  const steps = new Map<string, Step>()
  for (const event of events) {
    if (event.type !== 'tool_call' && event.type !== 'tool_result') continue
    const key = `${event.tool}:${event.input.cnpj}`
    if (event.type === 'tool_call' && !steps.has(key)) {
      steps.set(key, { key, tool: event.tool, cnpj: event.input.cnpj, status: 'running' })
    } else if (event.type === 'tool_result') {
      const step = steps.get(key)
      if (step) step.status = event.ok ? 'ok' : 'error'
    }
  }
  return [...steps.values()]
}
