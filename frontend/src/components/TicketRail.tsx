import { TICKET_TYPE_LABEL } from '../agents'
import type { Ticket } from '../types'

const PHASE_LABEL = {
  open: 'Open',
  running: 'Team working',
  awaiting_approval: 'Needs your approval',
  resolved: 'Resolved',
} as const

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
}

export default function TicketRail({ tickets, selectedId, onSelect }: Props) {
  const resolved = tickets.filter((t) => t.state === 'resolved').length
  return (
    <nav className="rail" aria-label="Tickets">
      <div className="rail-head">
        <h2>The board</h2>
        <span className="tally">
          {resolved}/{tickets.length} resolved
        </span>
      </div>
      <div className="rail-progress" aria-hidden>
        <span style={{ width: tickets.length ? `${(resolved / tickets.length) * 100}%` : 0 }} />
      </div>

      <ul>
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              className={`stub phase-${t.phase} ${t.id === selectedId ? 'selected' : ''}`}
              onClick={() => onSelect(t.id)}
              aria-current={t.id === selectedId}
            >
              <span className="stub-no">
                <small>№</small>
                {t.id}
              </span>
              <span className="stub-body">
                <span className="stub-type">{TICKET_TYPE_LABEL[t.type] ?? t.type}</span>
                <span className="stub-subject">{t.subject}</span>
                <span className="stub-who">{t.requester}</span>
                <span className={`phase-chip ${t.phase}`}>
                  <span className="dot" />
                  {PHASE_LABEL[t.phase]}
                </span>
              </span>
              {t.phase === 'resolved' && <span className="stamp" aria-hidden>Resolved</span>}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
