import type { Approval, Cash, FeedEvent, Health, Ticket, TicketSummary } from './types'

// The FastAPI backend from Problem 7 (backend/main.py). Set in frontend/.env.
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
  }
  return body as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  tickets: () => request<{ date_today: string; tickets: Ticket[] }>('/api/tickets'),
  summary: (id: number) => request<TicketSummary>(`/api/tickets/${id}/summary`),
  run: (id: number) =>
    request<{ team_run_id: string; ticket_id: number; status: string }>(`/api/tickets/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ instructions: '' }),
    }),
  events: (teamRunId: string) =>
    request<{ active_run: string | null; events: FeedEvent[] }>(
      `/api/events?limit=1000&team_run_id=${encodeURIComponent(teamRunId)}`,
    ),
  approvals: () => request<{ approvals: Approval[] }>('/api/approvals?status=pending'),
  approve: (id: number, approvedBy: string) =>
    request<{ new_balance: number; ticket_resolved: boolean }>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (id: number, approvedBy: string, reason: string) =>
    request<unknown>(`/api/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy, reason }),
    }),
  cash: () => request<Cash>('/api/cash'),
  reset: () => request<{ ok: boolean; message: string }>('/api/reset', { method: 'POST' }),
}
