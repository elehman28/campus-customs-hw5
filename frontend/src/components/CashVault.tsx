import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'
import type { Cash } from '../types'

/** Tween a number so the balance visibly rolls down after a payment. */
function useRolling(value: number | undefined, ms = 1400) {
  const [shown, setShown] = useState(value ?? 0)
  const from = useRef(value ?? 0)
  useEffect(() => {
    if (value == null) return
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const ease = 1 - Math.pow(1 - t, 4)
      setShown(a + (value - a) * ease)
      if (t < 1) raf = requestAnimationFrame(tick)
      else from.current = value
    }
    raf = requestAnimationFrame(tick)
    // Background tabs pause requestAnimationFrame; always land on the real balance.
    const settle = setTimeout(() => {
      setShown(value)
      from.current = value
    }, ms + 50)
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(settle)
    }
  }, [value, ms])
  return shown
}

export default function CashVault({ cash }: { cash: Cash | null }) {
  const shown = useRolling(cash?.balance)
  const [flash, setFlash] = useState(false)
  const prev = useRef<number | null>(null)
  useEffect(() => {
    if (cash && prev.current != null && cash.balance < prev.current) {
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 1600)
      return () => clearTimeout(t)
    }
    if (cash) prev.current = cash.balance
  }, [cash])
  useEffect(() => {
    if (cash) prev.current = cash.balance
  }, [cash])

  const [dollars, cents] = money(shown).split('.')
  const pending = cash?.pending_approval_total ?? 0
  const balance = cash?.balance ?? 0
  const pendingPct = balance > 0 ? Math.min(100, (pending / balance) * 100) : 0
  const after = cash?.balance_if_all_pending_paid ?? 0

  return (
    <section className={`panel vault ${flash ? 'flash' : ''}`} aria-label="Checking balance">
      <div className="vault-head">
        <h3>Checking</h3>
        <span className="muted">cash_accounts · as of {cash?.as_of ?? '…'}</span>
      </div>
      <div className="balance" aria-live="polite">
        {dollars}
        <span className="cents">.{cents ?? '00'}</span>
      </div>
      <div className="runway" aria-hidden>
        <span className="runway-left" style={{ width: `${100 - pendingPct}%` }} />
        <span className="runway-pending" style={{ width: `${pendingPct}%` }} />
      </div>
      <div className="runway-legend">
        <span>
          <i className="sw left" /> Free {money(Math.max(0, after))}
        </span>
        <span>
          <i className="sw pend" /> Waiting on you {money(pending)}
        </span>
      </div>
      {after < 0 && <p className="warn">Approving everything would overdraw checking. Pick what to pay.</p>}
      <p className="vault-foot">Money only goes out. Nothing comes in, so every approval is final.</p>
    </section>
  )
}
