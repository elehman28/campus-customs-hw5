import { useEffect, useRef } from 'react'
import { AGENTS } from '../agents'
import type { FeedEvent } from '../types'

const time = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })

function fmtArgs(args: Record<string, unknown> | null | undefined) {
  if (!args) return ''
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? (v.length > 28 ? `"${v.slice(0, 28)}…"` : `"${v}"`) : JSON.stringify(v)}`)
    .join(', ')
}

export default function LiveWire({ events, running }: { events: FeedEvent[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [events.length, running])

  if (!events.length) {
    return (
      <div className="wire empty-wire">
        <div className="wire-empty-art" aria-hidden>
          <span /> <span /> <span />
        </div>
        <p>No run yet on this ticket. Press <b>Run the team</b> and the agents' conversation streams in here.</p>
      </div>
    )
  }

  return (
    <div className="wire" aria-live="polite">
      {events.map((e, i) => {
        const meta = e.agent ? AGENTS[e.agent] : null
        const style = meta ? ({ ['--c' as string]: meta.color } as React.CSSProperties) : undefined

        if (e.event === 'team_run_started' || e.event === 'team_run_finished') {
          return (
            <div key={i} className="wire-divider">
              <span>
                {e.event === 'team_run_started' ? 'Run started' : e.ok ? 'Run finished' : `Run stopped: ${e.error ?? 'error'}`} · {time(e.time)}
              </span>
            </div>
          )
        }
        if (e.event === 'delegation' && meta && e.to_agent) {
          const to = AGENTS[e.to_agent]
          return (
            <div key={i} className={`handoff ${e.allowed ? '' : 'refused'}`} style={{ ['--c' as string]: meta.color, ['--c2' as string]: to.color } as React.CSSProperties}>
              <div className="handoff-route">
                <span className="who" style={{ color: meta.color }}>{meta.label}</span>
                <span className="arrow">⟶</span>
                <span className="who" style={{ color: to.color }}>{to.label}</span>
                <span className="when">{time(e.time)}</span>
              </div>
              <p>{e.said}</p>
              {!e.allowed && <p className="refusal">Refused: {e.refused_reason}</p>}
            </div>
          )
        }
        if (!meta) return null

        if (e.event === 'agent_started') {
          return (
            <div key={i} className="wire-note" style={style}>
              <span className="mini-avatar">{meta.mono}</span> {meta.label} picked up the task
            </div>
          )
        }
        if (e.event === 'agent_failed') {
          return (
            <div key={i} className="msg error" style={style}>
              <span className="mini-avatar">{meta.mono}</span>
              <div><b>{meta.label}</b> hit a problem: {e.error}</div>
            </div>
          )
        }
        if (e.event === 'step' && e.tool_results) {
          return (
            <details key={i} className="results" style={style}>
              <summary>
                ↳ {e.tool_results.length} tool result{e.tool_results.length > 1 ? 's' : ''} for {meta.label}:{' '}
                {e.tool_results.map((r) => r.tool).join(', ')}
              </summary>
              {e.tool_results.map((r, j) => (
                <pre key={j}>
                  <b>{r.tool}</b>
                  {'\n'}
                  {r.result}
                </pre>
              ))}
            </details>
          )
        }
        if (e.event === 'step' && (e.said || e.tools?.length)) {
          return (
            <div key={i} className={`msg voice-${meta.voice} ${e.outcome ? 'final' : ''}`} style={style}>
              <span className="avatar-sm">{meta.mono}</span>
              <div className="msg-body">
                <div className="msg-head">
                  <b>{meta.label}</b>
                  {e.outcome && <span className={`outcome o-${e.outcome}`}>{e.outcome.replace('_', ' ')}</span>}
                  <span className="when">{time(e.time)}</span>
                </div>
                {e.said && <p>{e.said}</p>}
                {e.tools && e.tools.length > 0 && (
                  <div className="tool-chips">
                    {e.tools.map((t, j) => (
                      <code key={j} className={`chip ${t.tool === 'delegate_task' ? 'delegate' : ''}`}>
                        <span className="fn">{t.tool}</span>({fmtArgs(t.args)})
                      </code>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        }
        return null
      })}
      {running && (
        <div className="typing">
          <span /> <span /> <span />
        </div>
      )}
      <div ref={end} />
    </div>
  )
}
