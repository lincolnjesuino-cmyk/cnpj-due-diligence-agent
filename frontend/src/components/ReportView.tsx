import { maskCnpj } from '../cnpj'
import type { ActivityFit, CompanyProfile, Report, RiskLevel } from '../types'

const LEVEL_LABEL: Record<RiskLevel, string> = {
  LOW: 'Low risk',
  MEDIUM: 'Medium risk',
  HIGH: 'High risk',
  CRITICAL: 'Critical risk',
}

const FIT_LABEL: Record<ActivityFit, string> = {
  compatible: 'Compatible',
  partial: 'Partially compatible',
  incompatible: 'Not compatible',
  not_evaluated: 'Not evaluated (no purpose given)',
}

// Receita Federal publishes registration status in Portuguese.
const STATUS_LABEL: Record<string, string> = {
  ATIVA: 'Active',
  BAIXADA: 'Closed',
  INAPTA: 'Unfit',
  SUSPENSA: 'Suspended',
  NULA: 'Void',
}

const brl = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'BRL' })

function formatDate(iso?: string): string {
  if (!iso) return '—'
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function CompanyFacts({ company }: { company: CompanyProfile }) {
  return (
    <dl className="facts">
      <div>
        <dt>Status</dt>
        <dd className={company.status === 'ATIVA' ? 'ok' : 'bad'} title={company.status}>
          {STATUS_LABEL[company.status] ?? company.status}
        </dd>
      </div>
      <div>
        <dt>Opened</dt>
        <dd>{formatDate(company.opened_on)}</dd>
      </div>
      <div>
        <dt>Share capital</dt>
        <dd>{company.share_capital != null ? brl.format(company.share_capital) : '—'}</dd>
      </div>
      <div>
        <dt>Location</dt>
        <dd>{[company.city, company.state].filter(Boolean).join(', ') || '—'}</dd>
      </div>
      <div className="facts__wide">
        <dt>Primary activity (CNAE, as registered)</dt>
        <dd>
          {company.main_activity_code} — {company.main_activity}
        </dd>
      </div>
    </dl>
  )
}

export function ReportView({ report }: { report: Report }) {
  const { company, risk, narrative, sanctions } = report

  return (
    <article className="report" aria-label="Due diligence report">
      <header className="report__header">
        <div>
          <p className="eyebrow">CNPJ {maskCnpj(company.cnpj)}</p>
          <h2 className="report__title">{company.legal_name}</h2>
        </div>
        <div className={`risk risk--${risk.level.toLowerCase()}`}>
          <span className="risk__level">{LEVEL_LABEL[risk.level]}</span>
          <span className="risk__score">{risk.score} pts</span>
        </div>
      </header>

      <p className="report__summary">{narrative.summary}</p>

      <CompanyFacts company={company} />

      <div className="report__grid">
        <section>
          <h3 className="section-label">Risk signals</h3>
          {risk.signals.length === 0 ? (
            <p className="muted">No risk signals triggered.</p>
          ) : (
            <ul className="signals">
              {risk.signals.map((s) => (
                <li key={s.code} className={`signal signal--${s.severity}`}>
                  <span className="signal__points">{s.points > 0 ? `+${s.points}` : 'i'}</span>
                  <span>
                    {s.message}
                    <span className="signal__source">Source: {s.source}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!risk.complete && (
            <p className="warning">Incomplete assessment: one of the sources could not be checked.</p>
          )}
          <p className="muted small">
            {sanctions.checked
              ? `${sanctions.sanctions.length} record(s) on CEIS/CNEP.`
              : 'CEIS/CNEP not checked.'}{' '}
            The score comes from fixed, unit-tested rules — not from the model.
          </p>
        </section>

        <section>
          <h3 className="section-label">Fit with your purpose</h3>
          <p className={`fit fit--${narrative.activity_fit}`}>{FIT_LABEL[narrative.activity_fit]}</p>
          <p>{narrative.activity_fit_reason}</p>
        </section>
      </div>

      {narrative.attention_points.length > 0 && (
        <section>
          <h3 className="section-label">Points of attention</h3>
          <ul className="bullets">
            {narrative.attention_points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="section-label">Recommended next steps</h3>
        <ol className="bullets">
          {narrative.recommendations.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ol>
      </section>

      {report.related_companies.length > 0 && (
        <section>
          <h3 className="section-label">Shareholder companies investigated</h3>
          {report.related_companies.map((c) => (
            <div key={c.cnpj} className="related">
              <p>
                <strong>{c.legal_name}</strong> <span className="muted">{maskCnpj(c.cnpj)}</span>
              </p>
              <CompanyFacts company={c} />
            </div>
          ))}
        </section>
      )}

      <footer className="report__footer">
        <h3 className="section-label">Sources</h3>
        <ul className="sources">
          {report.sources.map((s) => (
            <li key={`${s.url}-${s.consulted_at}`}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.name}
              </a>
              <span className="muted"> · {new Date(s.consulted_at).toLocaleString('en-US')}</span>
            </li>
          ))}
        </ul>
        <p className="muted small">
          Written by {report.model} from official public data. Not legal advice.
        </p>
      </footer>
    </article>
  )
}
