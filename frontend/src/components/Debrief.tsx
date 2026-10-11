import { AGENTS } from '../agents'
import type { TicketSummary } from '../types'

export default function Debrief({ summary }: { summary: TicketSummary | null }) {
  if (!summary || !summary.last_run) {
    return <div className="debrief empty-debrief">The debrief appears once the team has run on this ticket.</div>
  }
  if (!summary.last_run.finished) {
    return <div className="debrief empty-debrief">The team is still working. The debrief is written when the run ends.</div>
  }
  const path = summary.delegations.filter((d) => d.allowed)
  return (
    <div className="debrief">
      <div className="debrief-top">
        <div className="route">
          {path.length ? (
            path.map((d, i) => (
              <span key={i} className="route-step">
                <span style={{ color: AGENTS[d.from].color }}>{AGENTS[d.from].label}</span>
                <span className="arrow">→</span>
                <span style={{ color: AGENTS[d.to].color }}>{AGENTS[d.to].label}</span>
              </span>
            ))
          ) : (
            <span className="muted">Boss handled it without hand-offs.</span>
          )}
        </div>
        {summary.usage && (
          <div className="usage">
            <span><b>{summary.usage.model_requests}</b> model calls</span>
            <span><b>{summary.usage.tool_calls}</b> tool calls</span>
            <span><b>{(summary.usage.input_tokens + summary.usage.output_tokens).toLocaleString()}</b> tokens</span>
          </div>
        )}
      </div>

      <div className="debrief-grid">
        {summary.agents.map((a) => {
          const meta = AGENTS[a.agent]
          return (
            <article key={a.agent} className="debrief-card" style={{ ['--c' as string]: meta.color } as React.CSSProperties}>
              <header>
                <span className="avatar-sm">{meta.mono}</span>
                <div>
                  <b>{meta.label}</b>
                  <small>{meta.role}</small>
                </div>
                {a.outcome && <span className={`outcome o-${a.outcome}`}>{a.outcome.replace('_', ' ')}</span>}
              </header>
              <p>{a.summary || 'No summary returned.'}</p>
              {a.actions_taken.length > 0 && (
                <ul className="actions">
                  {a.actions_taken.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              )}
              <div className="tool-chips">
                {a.tools.map((t) => (
                  <code key={t} className={`chip ${t === 'delegate_task' ? 'delegate' : ''}`}>
                    <span className="fn">{t}</span>
                  </code>
                ))}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
