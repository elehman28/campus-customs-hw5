import type { AgentName } from './types'

export interface AgentMeta {
  name: AgentName
  label: string
  mono: string
  color: string
  role: string
  voice: 'memo' | 'ledger' | 'plain' | 'warm'
}

// Each agent has its own color, monogram, and "voice" (how its lines are typeset in the wire).
export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { name: 'boss', label: 'Boss', mono: 'B', color: '#ff4fa3', role: 'Runs the board', voice: 'memo' },
  inventory: { name: 'inventory', label: 'Inventory', mono: 'In', color: '#4fe0c3', role: 'Stock & vendors', voice: 'plain' },
  accounting: { name: 'accounting', label: 'Accounting', mono: 'Ac', color: '#ffc95c', role: 'Cash & invoices', voice: 'ledger' },
  facilities: { name: 'facilities', label: 'Facilities', mono: 'Fa', color: '#a99bff', role: 'Lease & rent', voice: 'plain' },
  customer_service: { name: 'customer_service', label: 'Customer Service', mono: 'CS', color: '#6cc8ff', role: 'Customer drafts', voice: 'warm' },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const TICKET_TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
