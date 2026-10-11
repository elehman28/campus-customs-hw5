import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { Approval, Cash, FeedEvent, Health, Ticket, TicketSummary } from './types'
import Header from './components/Header'
import TicketRail from './components/TicketRail'
import TicketHero from './components/TicketHero'
import AgentFloor, { deriveFloor } from './components/AgentFloor'
import LiveWire from './components/LiveWire'
import Debrief from './components/Debrief'
import CashVault from './components/CashVault'
import ApprovalQueue from './components/ApprovalQueue'
import Toasts, { type Toast } from './components/Toasts'

const BOARD_POLL_MS = 2500
const RUN_POLL_MS = 1200

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [dateToday, setDateToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [backendDown, setBackendDown] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [tab, setTab] = useState<'wire' | 'debrief'>('wire')
  const [starting, setStarting] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((all) => [...all, { ...t, id }])
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), 5200)
  }, [])

  // ---- Board: tickets, cash, approvals -------------------------------------------------
  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setTickets(t.tickets)
      setDateToday(t.date_today)
      setCash(c)
      setApprovals(a.approvals)
      setBackendDown(false)
      setSelectedId((id) => id ?? t.tickets[0]?.id ?? null)
    } catch {
      setBackendDown(true)
    }
  }, [])

  useEffect(() => {
    refreshBoard()
    const t = setInterval(refreshBoard, BOARD_POLL_MS)
    return () => clearInterval(t)
  }, [refreshBoard])

  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null))
    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [])

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const runId = selected?.last_run?.team_run_id ?? null
  const running = selected?.phase === 'running' || (!!selected?.last_run && !selected.last_run.finished)
  const anyRunning = tickets.some((t) => t.phase === 'running')

  // ---- Live wire: events for the selected ticket's latest run --------------------------
  useEffect(() => {
    setEvents([])
    if (!runId) return
    let alive = true
    const load = () =>
      api
        .events(runId)
        .then((r) => alive && setEvents([...r.events].reverse()))
        .catch(() => undefined)
    load()
    const t = running ? setInterval(load, RUN_POLL_MS) : undefined
    return () => {
      alive = false
      if (t) clearInterval(t)
    }
  }, [runId, running])

  // ---- Debrief: per-agent summary once a run has finished ------------------------------
  const finishedKey = `${selectedId}:${runId}:${selected?.last_run?.finished}:${selected?.status}`
  useEffect(() => {
    if (selectedId == null) return
    api.summary(selectedId).then(setSummary).catch(() => setSummary(null))
  }, [finishedKey, selectedId])

  // Flip to the debrief automatically when a run we were watching finishes.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !running && runId) {
      setTab('debrief')
      toast({ tone: 'ok', title: `Ticket ${selectedId}: the team is done`, body: 'Debrief is ready.' })
    }
    wasRunning.current = running
  }, [running, runId, selectedId, toast])

  const floor = useMemo(() => deriveFloor(events), [events])

  // ---- Actions -------------------------------------------------------------------------
  const startRun = async () => {
    if (!selected) return
    setStarting(true)
    try {
      await api.run(selected.id)
      setTab('wire')
      toast({ tone: 'info', title: `Team dispatched on ticket ${selected.id}`, body: 'Boss is reading the ticket.' })
      await refreshBoard()
    } catch (e) {
      toast({ tone: 'error', title: 'Could not start the team', body: (e as Error).message })
    } finally {
      setStarting(false)
    }
  }

  const approve = async (a: Approval, name: string) => {
    const before = cash?.balance
    try {
      const r = await api.approve(a.id, name)
      toast({
        tone: 'ok',
        title: `Paid ${a.payee}`,
        body: `Checking ${before != null ? `${fmt(before)} → ` : ''}${fmt(r.new_balance)}${r.ticket_resolved ? ` · ticket ${a.ticket_id} resolved` : ''}`,
      })
    } catch (e) {
      toast({ tone: 'error', title: 'Payment refused', body: (e as Error).message })
    }
    await refreshBoard()
  }

  const reject = async (a: Approval, name: string) => {
    try {
      await api.reject(a.id, name, 'Rejected from the ops desk')
      toast({ tone: 'info', title: `Rejected #${a.id}`, body: 'No money moved.' })
    } catch (e) {
      toast({ tone: 'error', title: 'Could not reject', body: (e as Error).message })
    }
    await refreshBoard()
  }

  const reset = async () => {
    try {
      const r = await api.reset()
      setEvents([])
      setSummary(null)
      toast({ tone: 'info', title: 'Shop reset', body: r.message })
    } catch (e) {
      toast({ tone: 'error', title: 'Reset failed', body: (e as Error).message })
    }
    await refreshBoard()
  }

  return (
    <div className="app">
      <div className="backdrop" aria-hidden />
      <Header dateToday={dateToday} health={health} backendDown={backendDown} canReset={!anyRunning} onReset={reset} />

      <main className="layout">
        <TicketRail tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />

        <section className="center">
          {selected ? (
            <>
              <TicketHero
                ticket={selected}
                running={running}
                starting={starting}
                blockedReason={
                  backendDown
                    ? 'Backend is offline at localhost:8000.'
                    : health && !health.ready_to_run
                      ? health.not_ready_reason
                      : anyRunning && !running
                        ? 'Another ticket is running. One team run at a time.'
                        : null
                }
                onRun={startRun}
              />
              <AgentFloor floor={floor} running={running} />
              <div className="panel feed-panel">
                <div className="tabs" role="tablist" aria-label="Run views">
                  <button role="tab" aria-selected={tab === 'wire'} className={tab === 'wire' ? 'on' : ''} onClick={() => setTab('wire')}>
                    <span className={`dot ${running ? 'live' : ''}`} /> Live wire
                  </button>
                  <button role="tab" aria-selected={tab === 'debrief'} className={tab === 'debrief' ? 'on' : ''} onClick={() => setTab('debrief')}>
                    Debrief
                  </button>
                </div>
                {tab === 'wire' ? <LiveWire events={events} running={running} /> : <Debrief summary={summary} />}
              </div>
            </>
          ) : (
            <div className="panel empty">{backendDown ? 'Waiting for the backend at localhost:8000…' : 'Loading the board…'}</div>
          )}
        </section>

        <aside className="right">
          <CashVault cash={cash} />
          <ApprovalQueue approvals={approvals} cash={cash} onApprove={approve} onReject={reject} onSelectTicket={setSelectedId} />
        </aside>
      </main>

      <Toasts toasts={toasts} />
    </div>
  )
}

const fmt = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
