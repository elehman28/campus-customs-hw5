import { useState } from 'react'
import type { Health } from '../types'

interface Props {
  dateToday: string
  health: Health | null
  backendDown: boolean
  canReset: boolean
  onReset: () => void
}

export default function Header({ dateToday, health, backendDown, canReset, onReset }: Props) {
  const [confirming, setConfirming] = useState(false)
  const d = dateToday ? new Date(`${dateToday}T12:00:00`) : null
  const status = backendDown ? 'offline' : health?.ready_to_run ? 'ready' : 'setup'

  return (
    <header className="header">
      <div className="brand">
        <div className="seal" aria-hidden>CC</div>
        <div>
          <h1>
            Campus Customs <em>Ops Desk</em>
          </h1>
          <p>Five agents, one board, and a human with the checkbook.</p>
        </div>
      </div>

      <div className="header-right">
        {d && (
          <div className="desk-date" title="desk.date_today: the shop's 'today'">
            <span className="dd-month">{d.toLocaleDateString('en-US', { month: 'short' })}</span>
            <span className="dd-day">{d.getDate()}</span>
            <span className="dd-week">{d.toLocaleDateString('en-US', { weekday: 'short' })} · {d.getFullYear()}</span>
          </div>
        )}
        <div className={`status-pill ${status}`}>
          <span className="dot" />
          {status === 'offline' ? 'Backend offline' : status === 'ready' ? 'Team on shift' : 'Setup needed'}
          {health && <span className="model">{health.model}</span>}
        </div>
        {confirming ? (
          <div className="reset-confirm">
            <span>Restore original shop data?</span>
            <button className="btn danger sm" onClick={() => { setConfirming(false); onReset() }}>Reset</button>
            <button className="btn ghost sm" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        ) : (
          <button className="btn ghost sm" disabled={!canReset} onClick={() => setConfirming(true)} title={canReset ? 'Copy the original database over the working copy' : 'Wait for the run to finish'}>
            ↺ Reset shop
          </button>
        )}
      </div>
    </header>
  )
}
