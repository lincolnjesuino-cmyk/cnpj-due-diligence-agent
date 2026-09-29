import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { buildSteps } from './components/steps'
import { DEMO_EVENTS } from './demo'

describe('App', () => {
  it('only enables Analyze for a valid CNPJ', async () => {
    const user = userEvent.setup()
    render(<App />)
    const button = screen.getByRole('button', { name: 'Analyze' })
    const input = screen.getByLabelText('CNPJ')

    await user.type(input, '33000167000102')
    expect(button).toBeDisabled()
    expect(screen.getByText(/Invalid CNPJ/)).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, '33000167000101')
    expect(input).toHaveValue('33.000.167/0001-01')
    expect(button).toBeEnabled()
  })

  it('replays the demo investigation and renders the report', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: /Run the demo/ }))

    const report = await screen.findByRole(
      'article',
      { name: 'Due diligence report' },
      { timeout: 15_000 },
    )
    expect(within(report).getByText('SERVICOS NOVOS LTDA')).toBeInTheDocument()
    expect(within(report).getByText('Medium risk')).toBeInTheDocument()
    expect(within(report).getByText('Partially compatible')).toBeInTheDocument()
    expect(screen.getByText('Demo · fictional companies')).toBeInTheDocument()
  }, 20_000)
})

describe('buildSteps', () => {
  it('pairs each tool call with its result', () => {
    const steps = buildSteps(DEMO_EVENTS)
    expect(steps).toHaveLength(5)
    expect(steps.every((s) => s.status === 'ok')).toBe(true)
  })

  it('keeps a call without result as running', () => {
    const [first] = DEMO_EVENTS
    expect(buildSteps(first ? [first] : [])[0]?.status).toBe('running')
  })
})
