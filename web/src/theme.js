/**
 * Presentation only. The *state machine* is the server's (`statuses` in the
 * payload); what lives here is what colour a status happens to be drawn in, and
 * a colour is not a rule. Keeping those two apart is the difference between
 * restyling the board and redefining it.
 */
export const STATUS_COLOR = {
  backlog: '#94a3b8', ready: '#60a5fa', doing: '#f59e0b', review: '#a78bfa',
  done: '#34d399', blocked: '#ef4444', dropped: '#9ca3af',
}
export const STATUS_TYPE = {
  backlog: 'info', ready: 'primary', doing: 'warning', review: 'primary',
  done: 'success', blocked: 'danger', dropped: 'info',
}
export const PRIORITY_TYPE = { high: 'danger', medium: 'warning', low: 'info' }
export const MAIL_STATE_TYPE = { acked: 'success', claimed: 'warning', unread: 'info' }

export const color = (status) => STATUS_COLOR[status] || '#94a3b8'

/** Dates arrive as plain YYYY-MM-DD. Daylight savings is not this project's problem. */
export const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000)
export const today = () => new Date().toISOString().slice(0, 10)
export const isOverdue = (due, status, terminal) =>
  !!due && due < today() && !(terminal || []).includes(status)
