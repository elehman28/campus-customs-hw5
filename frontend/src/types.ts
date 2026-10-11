export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type Phase = 'open' | 'running' | 'awaiting_approval' | 'resolved'

export interface LastRun {
  team_run_id: string
  started_at: string
  finished: boolean
  ok: boolean | null
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
  phase: Phase
  last_run: LastRun | null
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  pending_approval_total: number
  balance_if_all_pending_paid: number
}

export interface Approval {
  id: number
  ticket_id: number
  kind: 'invoice' | 'rent'
  ref_id: number
  amount: number
  payee: string
  reason: string | null
  requested_by: AgentName
  status: 'pending' | 'paid' | 'rejected'
  decided_by: string | null
  created_on: string
}

export interface FeedEvent {
  time: string
  team_run_id: string | null
  agent: AgentName | null
  event: string
  said?: string
  tools?: { tool: string; args: Record<string, unknown> | null }[]
  tool_results?: { tool: string; result: string }[]
  to_agent?: AgentName
  allowed?: boolean
  refused_reason?: string | null
  outcome?: string
  task?: string
  error?: string
  ok?: boolean
  model?: string
  ticket_id?: number
  decision?: string
  decided_by?: string
  reason?: string
}

export interface AgentSummary {
  agent: AgentName
  tasks: string[]
  tools: string[]
  summary: string
  outcome: string | null
  actions_taken: string[]
  steps: number
}

export interface TicketSummary {
  ticket: Ticket
  linked: Record<string, unknown>
  last_run: LastRun | null
  agents: AgentSummary[]
  delegations: { from: AgentName; to: AgentName; task: string; allowed: boolean }[]
  usage: { model_requests: number; tool_calls: number; input_tokens: number; output_tokens: number } | null
}

export interface Health {
  ok: boolean
  model: string
  ready_to_run: boolean
  not_ready_reason: string | null
}
