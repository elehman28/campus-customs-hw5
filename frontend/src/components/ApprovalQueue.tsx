import { useState } from 'react'
import { AGENTS, money } from '../agents'
import type { Approval, Cash } from '../types'

interface Props {
  approvals: Approval[]
  cash: Cash | null
  onApprove: (a: Approval, name: string) => Promise<void>
  onReject: (a: Approval, name: string) => Promise<void>
  onSelectTicket: (id: number) => void
}

export default function ApprovalQueue({ approvals, cash, onApprove, onReject, onSelectTicket }: Props) {
  const [name, setName] = useState(() => localStorage.getItem('cc-approver') ?? '')
  const [busy, setBusy] = useState<number | null>(null)
  const save = (v: string) => {
    setName(v)
    localStorage.setItem('cc-approver', v)
  }
  const act = async (fn: typeof onApprove, a: Approval) => {
    setBusy(a.id)
    await fn(a, name.trim())
    setBusy(null)
  }

  return (
    <section className="panel queue" aria-label="Payments waiting for approval">
      <div className="vault-head">
        <h3>Needs your signature</h3>
        {approvals.length > 0 && <span className="badge">{approvals.length}</span>}
      </div>

      <label className="signer">
        <span>Signing as</span>
        <input value={name} onChange={(e) => save(e.target.value)} placeholder="Your name" maxLength={60} />
      </label>

      {approvals.length === 0 ? (
        <p className="muted queue-empty">Nothing waiting. When an agent prepares a payment, it lands here for a human to approve.</p>
      ) : (
        <ul className="cheques">
          {approvals.map((a) => {
            const meta = AGENTS[a.requested_by]
            const short = cash ? a.amount > cash.balance : false
            return (
              <li key={a.id} className="cheque">
                <div className="cheque-top">
                  <span className="cheque-no">Request #{a.id}</span>
                  <button className="link" onClick={() => onSelectTicket(a.ticket_id)}>
                    ticket №{a.ticket_id}
                  </button>
                </div>
                <div className="cheque-line">
                  <span className="payto">Pay to</span>
                  <b>{a.payee}</b>
                </div>
                <div className="cheque-amount">{money(a.amount)}</div>
                <div className="cheque-memo">
                  <span className="payto">Memo</span> {a.kind === 'invoice' ? `Invoice #${a.ref_id}` : `Rent · lease #${a.ref_id}`}
                  {a.reason ? `: ${a.reason}` : ''}
                </div>
                <div className="cheque-by">
                  prepared by <span style={{ color: meta.color }}>{meta.label}</span>
                  {cash && !short && <> · leaves {money(cash.balance - a.amount)}</>}
                </div>
                {short && <p className="warn">Not enough cash. The pay tool will refuse this.</p>}
                <div className="cheque-actions">
                  <button className="btn primary" disabled={!name.trim() || busy === a.id} onClick={() => act(onApprove, a)} title={name.trim() ? '' : 'Enter your name first'}>
                    {busy === a.id ? 'Paying…' : 'Approve & pay'}
                  </button>
                  <button className="btn ghost" disabled={!name.trim() || busy === a.id} onClick={() => act(onReject, a)}>
                    Reject
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
