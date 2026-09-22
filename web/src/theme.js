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

/**
 * The status vocabulary, same rule: the colour for a value, never a list of them.
 *
 * This map and `STATUS_LABEL` below are the *English* key set of the one label
 * dictionary `design/17-org-and-project.md` §4 describes: every user-visible word
 * resolves through a concept registry keyed by the raw token, and the raw token
 * stays canonical. The keys here are the protocol values exactly -- `backlog`,
 * `review`, `blocked` -- which is what `bin/aim task move --status` takes and what
 * the record holds.
 *
 * Three of the seven are their own name (`backlog`, `ready`, `done`), and that is
 * stated rather than tidied away. `doing -> "in progress"` and `review -> "in
 * review"` are names for the token, not replacements for it: every surface that
 * draws one still prints the token beside it (Help's token table, the Kanban
 * column, the filter options), so the word and the value it names are both on the
 * page and neither is a guess about the other.
 *
 * The server owns the same tokens (`statuses` in the payload, `TASK_STATUSES` in
 * `bin/aim`) and publishes a label for each through `concepts`
 * (`aimboard/api.py:253`, group `status`). `statusLabel` prefers that label when
 * the caller has the payload to hand, so the two cannot drift; this map is the
 * fallback for a surface that only has a token, because a blank label on a board
 * is worse than a stale one and the shell already says which build is serving.
 */
export const STATUS_LABEL = {
  backlog: 'backlog', ready: 'ready', doing: 'in progress', review: 'in review',
  done: 'done', blocked: 'blocked', dropped: 'dropped',
}

/**
 * The one lookup for a status token.
 *
 * `concepts` is the payload's registry (`board.doc.concepts`), and it wins when it
 * is passed: the server generated it out of the table the tool itself reads, which
 * makes it the authority for what a status is called. The local map answers when
 * there is no payload -- a pane rendered in a unit test, a server that predates the
 * key -- and the raw token answers last, because a token with no entry is a fact
 * about this build and printing it is more honest than printing an invented name.
 */
export const statusLabel = (status, concepts) => {
  const published = concepts && typeof concepts === 'object' ? concepts[status] : null
  if (published && typeof published === 'object' && published.label) return published.label
  return STATUS_LABEL[status] || status
}

export const MAIL_STATE_TYPE = { acked: 'success', claimed: 'warning', unread: 'info' }

export const color = (status) => STATUS_COLOR[status] || '#94a3b8'

/**
 * Dates arrive as plain `YYYY-MM-DD`, read as calendar days in the plan's zone
 * (`plan/plan.json:5`), and rendered by `dates.js` -- dates are the one thing in
 * this file with a rule attached, and the rule lives there.
 *
 * `today()` is the *reader's* day, and the place that makes that auditable is the
 * comparison below rather than this function: "overdue" asks whether a stored
 * calendar date is behind the current one, and a task on the record with no time
 * of day is not past midnight anywhere in particular. Measured, `today()` at
 * `2026-09-22T22:33+08:00` was `2026-09-22` in `Asia/Shanghai` and `2026-09-22`
 * in `UTC` -- the two zones this board's readers sit in agree on the current day
 * for sixteen hours of every twenty-four, and for the other eight the row can read
 * "late" one day early for a reader east of the store. That is a real limit of
 * comparing a zone-free date to *now*, it is the server's to settle (the payload's
 * `as_of` is the day the board was folded for, and `bin/aim` reads `as_of` the
 * same way), and it is left as it is here rather than papered over by a `today()`
 * that silently shifts.
 */
export const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000)
export const today = () => new Date().toISOString().slice(0, 10)
export const isOverdue = (due, status, terminal) =>
  !!due && due < today() && !(terminal || []).includes(status)
