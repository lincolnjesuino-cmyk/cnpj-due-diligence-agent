import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { analyze } from './api'
import { isValidCnpj, maskCnpj } from './cnpj'
import { Timeline } from './components/Timeline'
import { ReportView } from './components/ReportView'
import { DEMO_CNPJ, DEMO_PURPOSE, replayDemo } from './demo'
import type { AgentEvent, Language, Report } from './types'

type Status = 'idle' | 'running' | 'done' | 'error'

// The static build published to GitHub Pages has no backend: it only runs the demo.
const DEMO_ONLY = import.meta.env.VITE_DEMO_ONLY === 'true'

export default function App() {
  const [cnpj, setCnpj] = useState('')
  const [purpose, setPurpose] = useState('')
  const [language, setLanguage] = useState<Language>('en')
  const [status, setStatus] = useState<Status>('idle')
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDemo, setIsDemo] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const cnpjComplete = cnpj.replace(/\D/g, '').length === 14
  const cnpjInvalid = cnpjComplete && !isValidCnpj(cnpj)

  function onEvent(event: AgentEvent) {
    setEvents((prev) => [...prev, event])
    if (event.type === 'report') {
      setReport(event.report)
      setStatus('done')
    } else if (event.type === 'error') {
      setError(event.message)
      setStatus('error')
    }
  }

  async function start(demo: boolean) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setIsDemo(demo)
    setEvents([])
    setReport(null)
    setError(null)
    setStatus('running')
    try {
      if (demo) {
        setCnpj(DEMO_CNPJ)
        setPurpose(DEMO_PURPOSE)
        await replayDemo(onEvent, 650, controller.signal)
      } else {
        await analyze(cnpj, purpose, language, onEvent, controller.signal)
      }
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err instanceof Error ? err.message : 'Unexpected error.')
      setStatus('error')
    }
  }

  // Shareable link: ?demo plays the example as soon as the page opens.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has('demo')) void start(true)
    return () => abortRef.current?.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, [])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (DEMO_ONLY) return void start(true)
    if (!isValidCnpj(cnpj)) return
    void start(false)
  }

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">AI agent · KYB for Brazilian companies</p>
        <h1>
          Vendor due diligence, <em>in seconds.</em>
        </h1>
        <p className="lead">
          Give it a CNPJ — the Brazilian company registration number. A Claude agent pulls the
          official company registry and the federal debarment lists, investigates shareholder
          companies, and explains the risk of hiring, buying from or partnering with that company.
          Every fact is sourced; the risk score comes from deterministic rules.
        </p>
      </header>

      <form className="card form" onSubmit={onSubmit} noValidate>
        <label htmlFor="cnpj">CNPJ</label>
        <input
          id="cnpj"
          inputMode="numeric"
          autoComplete="off"
          placeholder="00.000.000/0000-00"
          value={cnpj}
          onChange={(e) => setCnpj(maskCnpj(e.target.value))}
          aria-invalid={cnpjInvalid}
          aria-describedby="cnpj-error"
          disabled={DEMO_ONLY}
        />
        <p id="cnpj-error" className="field-error" role="alert">
          {cnpjInvalid ? 'Invalid CNPJ: check digits do not match.' : ''}
        </p>

        <label htmlFor="purpose">
          Purpose <span className="muted">(optional)</span>
        </label>
        <input
          id="purpose"
          placeholder="e.g. hire them to refurbish a warehouse"
          maxLength={500}
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          disabled={DEMO_ONLY}
        />

        <div className="form__row">
          <label htmlFor="language">Report language</label>
          <select
            id="language"
            value={language}
            onChange={(e) => setLanguage(e.target.value as Language)}
            disabled={DEMO_ONLY}
          >
            <option value="en">English</option>
            <option value="pt">Português</option>
          </select>
        </div>

        <div className="form__actions">
          {!DEMO_ONLY && (
            <button
              type="submit"
              className="button"
              disabled={!isValidCnpj(cnpj) || status === 'running'}
            >
              {status === 'running' && !isDemo ? 'Analyzing…' : 'Analyze'}
            </button>
          )}
          <button
            type="button"
            className={DEMO_ONLY ? 'button' : 'button button--ghost'}
            onClick={() => void start(true)}
            disabled={status === 'running'}
          >
            Run the demo (fictional data)
          </button>
        </div>
        {DEMO_ONLY && (
          <p className="muted small">
            This hosted version only plays a recorded run. To analyze real companies, run the project
            locally with your own API key (see the README).
          </p>
        )}
      </form>

      {status !== 'idle' && (
        <main className="results">
          {isDemo && <p className="demo-badge">Demo · fictional companies</p>}
          <Timeline events={events} targetCnpj={cnpj} finished={status !== 'running'} />
          {error && (
            <p className="card error" role="alert">
              {error}
            </p>
          )}
          {report && <ReportView report={report} />}
        </main>
      )}

      <footer className="page__footer">
        <a href="https://github.com/lincolnjesuino-cmyk/cnpj-due-diligence-agent">Source on GitHub</a>
        <span>·</span>
        <a href="https://www.linkedin.com/in/lincolnmassari">Built by Lincoln Massari</a>
      </footer>
    </div>
  )
}
