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
/**
 * The priority vocabulary, as `bin/aim` defines it. Only entries the tool can
 * actually write appear here: the board derives its options from the payload, and
 * this map is the *colour* for a value that is there. A fallback of `info` covers
 * anything a future vocabulary adds, which is honest -- an unknown priority is
 * drawn as unknown rather than as a middle level nobody recorded.
 */
export const PRIORITY_TYPE = { high: 'danger', normal: 'warning', low: 'info' }

/** The status vocabulary, same rule: the colour for a value, never a list of them. */
export const STATUS_LABEL = {
  backlog: 'backlog', ready: 'ready', doing: 'in progress', review: 'in review',
  done: 'done', blocked: 'blocked', dropped: 'dropped',
}
export const statusLabel = (status) => STATUS_LABEL[status] || status

export const MAIL_STATE_TYPE = { acked: 'success', claimed: 'warning', unread: 'info' }

export const color = (status) => STATUS_COLOR[status] || '#94a3b8'

/** Dates arrive as plain YYYY-MM-DD. Daylight savings is not this project's problem. */
export const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000)
export const today = () => new Date().toISOString().slice(0, 10)
export const isOverdue = (due, status, terminal) =>
  !!due && due < today() && !(terminal || []).includes(status)
