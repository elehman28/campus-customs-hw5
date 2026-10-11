import { TICKET_TYPE_LABEL } from '../agents'
import type { Ticket } from '../types'

interface Props {
  ticket: Ticket
  running: boolean
  starting: boolean
  blockedReason: string | null
  onRun: () => void
}

export default function TicketHero({ ticket: t, running, starting, blockedReason, onRun }: Props) {
  const facts: [string, string][] = []
  if (t.sku) facts.push(['SKU', t.sku])
  if (t.size) facts.push(['Size', t.size])
  if (t.qty != null) facts.push(['Qty', String(t.qty)])
  if (t.invoice_id != null) facts.push(['Invoice', `#${t.invoice_id}`])
  if (t.lease_id != null) facts.push(['Lease', `#${t.lease_id}`])
  facts.push(['Filed', new Date(t.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })])

  const resolved = t.phase === 'resolved'
  const label = running ? 'Team is working…' : starting ? 'Dispatching…' : t.last_run ? 'Run the team again' : 'Run the team'

  return (
    <div className={`hero panel phase-${t.phase}`}>
      <div className="hero-text">
        <div className="hero-kicker">
          {TICKET_TYPE_LABEL[t.type] ?? t.type} · from {t.requester}
        </div>
        <h2>
          <span className="hero-no">№{t.id}</span> {t.subject}
        </h2>
        {t.notes && <p className="hero-notes">{t.notes.split('\n')[0]}</p>}
        <div className="facts">
          {facts.map(([k, v]) => (
            <span key={k} className="fact">
              <b>{k}</b> {v}
            </span>
          ))}
        </div>
      </div>
      <div className="hero-action">
        <button className={`btn primary run ${running ? 'busy' : ''}`} disabled={running || starting || resolved || !!blockedReason} onClick={onRun}>
          {running && <span className="spinner" aria-hidden />}
          {resolved ? '✓ Resolved' : label}
        </button>
        {blockedReason && !running && !resolved && <p className="blocked">{blockedReason}</p>}
        {t.phase === 'awaiting_approval' && <p className="hint">Payment request waiting in the vault →</p>}
      </div>
    </div>
  )
}
