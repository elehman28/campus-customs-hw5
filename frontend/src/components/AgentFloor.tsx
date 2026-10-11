import { AGENTS, AGENT_ORDER } from '../agents'
import type { AgentName, FeedEvent } from '../types'

type Status = 'idle' | 'thinking' | 'tool' | 'done' | 'error'

export interface AgentLive {
  status: Status
  tool?: string
  line?: string
  calls: number
}

export interface Floor {
  agents: Record<AgentName, AgentLive>
  edges: { from: AgentName; to: AgentName; allowed: boolean; active: boolean }[]
}

/** Replay a run's events into "who is doing what right now" and "who handed work to whom". */
export function deriveFloor(events: FeedEvent[]): Floor {
  const agents = Object.fromEntries(AGENT_ORDER.map((n) => [n, { status: 'idle', calls: 0 } as AgentLive])) as Record<AgentName, AgentLive>
  const edges: Floor['edges'] = []
  for (const e of events) {
    const a = e.agent ? agents[e.agent] : undefined
    switch (e.event) {
      case 'agent_started':
        if (a) Object.assign(a, { status: 'thinking', tool: undefined, line: 'Reading the task…' })
        break
      case 'step':
        if (!a) break
        if (e.tools?.length) {
          a.status = 'tool'
          a.tool = e.tools[e.tools.length - 1].tool
          a.calls += e.tools.length
          a.line = e.said || `Calling ${e.tools.map((t) => t.tool).join(', ')}`
        } else if (e.tool_results) {
          a.status = 'thinking'
          a.line = 'Reading tool results…'
        } else if (e.outcome) {
          a.status = 'done'
          a.line = e.said
        } else if (e.said) {
          a.line = e.said
        }
        break
      case 'agent_finished':
        if (a) a.status = 'done'
        break
      case 'agent_failed':
        if (a) Object.assign(a, { status: 'error', line: e.error })
        break
      case 'delegation':
        if (e.agent && e.to_agent) edges.push({ from: e.agent, to: e.to_agent, allowed: !!e.allowed, active: false })
        break
    }
  }
  for (const edge of edges) {
    const target = agents[edge.to]
    edge.active = edge.allowed && (target.status === 'thinking' || target.status === 'tool')
  }
  return { agents, edges }
}

// Pentagon: Boss at the top, specialists around it. Percent coordinates inside the floor.
const POS: Record<AgentName, { x: number; y: number }> = {
  boss: { x: 50, y: 20 },
  inventory: { x: 85, y: 44 },
  accounting: { x: 71, y: 84 },
  customer_service: { x: 29, y: 84 },
  facilities: { x: 15, y: 44 },
}

const STATUS_TEXT: Record<Status, string> = {
  idle: 'Off the clock',
  thinking: 'Thinking',
  tool: 'Using a tool',
  done: 'Reported back',
  error: 'Hit a problem',
}

export default function AgentFloor({ floor, running }: { floor: Floor; running: boolean }) {
  const pairs: [AgentName, AgentName][] = []
  AGENT_ORDER.forEach((a, i) => AGENT_ORDER.slice(i + 1).forEach((b) => pairs.push([a, b])))

  return (
    <div className={`panel floor ${running ? 'is-running' : ''}`}>
      <div className="floor-head">
        <h3>The floor</h3>
        <span className="floor-legend">
          <span className="lg mesh" /> anyone can hand off <span className="lg used" /> hand-offs this run
        </span>
      </div>

      <div className="floor-stage">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="floor-lines" aria-hidden>
          <defs>
            {floor.edges.map((e, i) => (
              <linearGradient key={i} id={`g-${i}`} gradientUnits="userSpaceOnUse" x1={POS[e.from].x} y1={POS[e.from].y} x2={POS[e.to].x} y2={POS[e.to].y}>
                <stop offset="0%" stopColor={AGENTS[e.from].color} />
                <stop offset="100%" stopColor={AGENTS[e.to].color} />
              </linearGradient>
            ))}
          </defs>
          {pairs.map(([a, b]) => (
            <line key={`${a}-${b}`} x1={POS[a].x} y1={POS[a].y} x2={POS[b].x} y2={POS[b].y} className="mesh-line" vectorEffect="non-scaling-stroke" />
          ))}
          {floor.edges.map((e, i) => (
            <line
              key={i}
              x1={POS[e.from].x}
              y1={POS[e.from].y}
              x2={POS[e.to].x}
              y2={POS[e.to].y}
              stroke={e.allowed ? `url(#g-${i})` : '#ff5d5d'}
              className={`hand-off ${e.active ? 'active' : ''} ${e.allowed ? '' : 'refused'}`}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>

        {AGENT_ORDER.map((name) => {
          const meta = AGENTS[name]
          const live = floor.agents[name]
          return (
            <div
              key={name}
              className={`station st-${live.status}`}
              style={{ left: `${POS[name].x}%`, top: `${POS[name].y}%`, ['--c' as string]: meta.color }}
            >
              <div className="avatar">
                <span className="orbit" aria-hidden />
                {meta.mono}
              </div>
              <div className="st-name">{meta.label}</div>
              <div className="st-status">
                {live.status === 'tool' && live.tool ? <code>{live.tool}</code> : STATUS_TEXT[live.status]}
                {live.calls > 0 && <span className="calls">{live.calls} calls</span>}
              </div>
              {live.line && live.status !== 'idle' && <div className="st-bubble">{live.line}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
