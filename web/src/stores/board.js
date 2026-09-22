/**
 * The one store. It holds what the server sent, and derives everything else.
 *
 * Derivation lives here rather than in panes for the same reason the gate lives
 * in one place on the server: two panes computing "which tasks are overdue"
 * independently is two answers to one question, and the second one is the one
 * that will be wrong.
 */
import { defineStore } from 'pinia'
import { days, isOverdue, today } from '../theme'

/**
 * The priority vocabulary, most urgent first, as `bin/aim` defines it.
 *
 * A board that invents a middle has invented a state the tool cannot write. The
 * picker still offers only what the board actually holds (see `priorities`);
 * this is the *order*, and the fallback when the board has nothing recorded yet.
 */
const PRIORITY_ORDER = ['high', 'normal', 'low']

/** A scroll container is "at the top" if it is within this many pixels of it. */
const TOP_EPSILON = 2

/**
 * The DOM `input` types that hold something a person typed.
 *
 * A checkbox is an `<input>` whose `value` is the string "on" whether or not the
 * reader has touched it, so a rule that reads `input.value` without this list
 * finds unsent text in every unchecked box on the page and never updates the
 * board again. That is not a hypothetical: it is exactly how this rule first
 * behaved, and the Live pane's own tests caught it.
 */
const TEXT_INPUT_TYPES = new Set(['', 'text', 'search', 'url', 'tel', 'email', 'password', 'number'])

const holdsText = (el) => {
  const tag = (el.tagName || '').toLowerCase()
  if (tag === 'textarea') return (el.value || '').length > 0
  if (tag === 'input') return TEXT_INPUT_TYPES.has(el.type) && (el.value || '').length > 0
  return Boolean(el.isContentEditable) && (el.textContent || '').trim().length > 0
}

/**
 * Who is in the middle of something that a re-render would take away.
 *
 * The rule is narrow on purpose. "The user might be reading" is not a reason to
 * stop updating a dashboard: it is the reason every dashboard ends up showing a
 * number nobody believes. What is protected is a control that holds unsent text
 * and a view the reader has deliberately scrolled away from the top of. Every
 * other state a reload could disturb is preserved by *reloading the data under
 * the DOM* rather than by tearing the page down, so it does not need a veto.
 */
export function readingInterrupt() {
  const active = document.activeElement
  if (active && (holdsText(active) || (active.selectionStart ?? 0) !== (active.selectionEnd ?? 0))) {
    return { reason: 'a field has unsent text', kind: 'field', el: active }
  }
  for (const el of document.querySelectorAll('textarea, input, [contenteditable]')) {
    if (holdsText(el)) return { reason: 'a field has unsent text', kind: 'field', el }
  }
  const page = document.scrollingElement
  if (page && page.scrollTop > TOP_EPSILON) {
    return { reason: 'the page is scrolled', kind: 'scroll', el: page }
  }
  // Only elements that have actually been scrolled are asked what they are: a
  // `getComputedStyle` per node would be a full style pass on every poll.
  for (const el of document.querySelectorAll('*')) {
    if (el.scrollTop <= TOP_EPSILON) continue
    const { overflowY } = getComputedStyle(el)
    if (overflowY === 'auto' || overflowY === 'scroll') {
      return { reason: 'a reading pane is scrolled', kind: 'scroll', el }
    }
  }
  return null
}

function scrollableAncestors(el) {
  const out = []
  for (let node = el?.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if (overflowY === 'auto' || overflowY === 'scroll') out.push(node)
  }
  return out
}

/**
 * Re-read the record in place.
 *
 * Returns a function that puts the reading position back. The point is that a
 * change on the server is not an event the reader has to react to: the data
 * arrives, the DOM is patched rather than rebuilt, and the only visible sign is
 * that the board is current. No `location.reload`, because a reload throws away
 * the router state, the open drawer, the draft and the scroll position, and the
 * reader has to find their place again.
 */
function withReadingPosition(fn) {
  const active = document.activeElement
  const start = active && 'selectionStart' in active ? active.selectionStart : null
  const end = active && 'selectionEnd' in active ? active.selectionEnd : null
  const scrolled = scrollableAncestors(active)
    .map((box) => [box, box.scrollTop])
    .filter(([, top]) => top > 0)
  const page = document.scrollingElement?.scrollTop || 0
  const win = [window.scrollX, window.scrollY]
  fn()
  return () => {
    if (document.scrollingElement) document.scrollingElement.scrollTop = page
    window.scrollTo(win[0], win[1])
    for (const [box, top] of scrolled) box.scrollTop = top
    if (active && active.isConnected && start !== null && document.activeElement !== active) {
      try {
        active.focus({ preventScroll: true })
        active.setSelectionRange(start, end)
      } catch { /* a field that will not take focus back is not worth a broken refresh */ }
    }
  }
}

export const useBoard = defineStore('board', {
  state: () => ({
    doc: null,
    viewer: 'human',
    loading: false,
    error: '',
    /** Set only while an update is deliberately waiting for the reader. */
    deferred: false,
    deferredReason: '',
    fetchedAt: '',
    lastDigest: '',
  }),
  getters: {
    statuses: (s) => s.doc?.statuses || [],
    terminal: (s) => s.doc?.terminal || [],
    phase: (s) => s.doc?.phase || '-',
    milestones: (s) => s.doc?.milestones || {},
    register: (s) => s.doc?.register || {},
    agents: (s) => s.doc?.agents || {},
    /** design/06 R2: what the server will do with a write, declared not guessed. */
    write: (s) => s.doc?.write || { enabled: false, as: '' },
    canWrite: (s) => Boolean((s.doc?.write || {}).enabled),
    writer: (s) => (s.doc?.write || {}).as || '',
    tasks(s) {
      return Object.values(s.doc?.tasks || {}).sort((a, b) => (a.id < b.id ? -1 : 1))
    },
    byStatus() {
      const out = {}
      for (const st of this.statuses) out[st] = []
      for (const t of this.tasks) (out[t.status || 'backlog'] ||= []).push(t)
      for (const st of Object.keys(out)) {
        out[st].sort((a, b) => (a.due || '9999') < (b.due || '9999') ? -1 : 1)
      }
      return out
    },
    owners() {
      return [...new Set(this.tasks.map((t) => t.owner).filter(Boolean))].sort()
    },
    tags() {
      return [...new Set(this.tasks.flatMap((t) => t.tags || []))].sort()
    },
    /**
     * The priorities this board actually holds, most urgent first.
     *
     * Derived, never a hardcoded list: `aim task new --priority` accepts what it
     * accepts, and a picker that offers a value the tool cannot write is a filter
     * that can only ever return nothing. The vocabulary is still canonical
     * English (`aimboard` writes `high|normal|low`), and the *order* is the
     * canonical one so the options do not shuffle as the board changes.
     */
    priorities() {
      const held = new Set(this.tasks.map((t) => t.priority).filter(Boolean))
      const ordered = PRIORITY_ORDER.filter((p) => held.has(p))
      const rest = [...held].filter((p) => !PRIORITY_ORDER.includes(p)).sort()
      return ordered.length || rest.length ? [...ordered, ...rest] : [...PRIORITY_ORDER]
    },
    overdue() {
      return this.tasks.filter((t) => isOverdue(t.due, t.status, this.terminal))
    },
    dated() {
      return this.tasks.filter((t) => t.start || t.due)
    },
    /** Tasks a person has actually recorded, as opposed to a plan seed. */
    seedOnly() {
      return this.tasks.filter((t) => (t.provenance || '').includes('seed'))
    },
    recorded() {
      return this.tasks.filter((t) => !(t.provenance || '').includes('seed'))
    },
    horizon() {
      const dates = this.dated.flatMap((t) => [t.start, t.due].filter(Boolean))
      for (const m of Object.values(this.milestones)) if (m.due) dates.push(m.due)
      return dates.sort().length ? [dates.sort()[0], dates.sort().at(-1)] : [today(), today()]
    },
    report: (s) => s.doc?.reports || { series: [], throughput: [], blocked: [], median_cycle: null },
    conversation: (s) => s.doc?.conversation || { channels: [], rooms: [], mail: [], withheld: 0 },
    channels: (s) => s.doc?.channels || [],
    /**
     * One chronological flattening of every conversation shape. Overview's recent
     * rows and Chat's thread grouping must ask the same question once; two panes
     * flattening the same three lists is two answers that will drift.
     */
    conversationRows(s) {
      const rows = []
      for (const channel of this.conversation.channels) {
        for (const message of channel.messages || []) {
          rows.push({
            ...message,
            shape: 'channel',
            scope: channel.id,
            channel: channel.id,
            room: null,
            gated: Boolean(channel.gated),
            rule: channel.rule || '',
          })
        }
      }
      for (const room of this.conversation.rooms) {
        for (const message of room.messages || []) {
          rows.push({
            ...message,
            shape: 'room',
            scope: `${room.channel}/${room.id}`,
            channel: room.channel,
            room: room.id,
            visibility: room.visibility,
            rule: 'a room inherits the parent channel gate; draft by default, publishing is deliberate',
          })
        }
      }
      for (const message of this.conversation.mail) {
        rows.push({
          ...message,
          shape: 'direct',
          scope: `${message.from} ⇄ ${message.to}`,
          channel: null,
          room: null,
          rule: 'a direct message is a durable record with a receipt, not a chat window',
        })
      }
      return rows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
    },
    phaseRequests() {
      const byChannel = Object.fromEntries(this.channels.map((channel) => [channel.id, channel]))
      return this.conversationRows
        .filter((row) => row.shape === 'channel' && row.kind === 'request')
        .map((row) => {
          const channel = byChannel[row.channel] || {}
          const match = /^request:\s*([A-Z_]+)\s*->\s*([A-Z_]+)$/.exec(row.subject || '')
          return {
            ...row,
            fromPhase: match?.[1] || row.phase || channel.phase,
            targetPhase: match?.[2] || '',
            currentPhase: channel.phase || '',
            participants: channel.participants || [],
            leader: channel.leader || '',
          }
        })
        .filter((request) => request.targetPhase && request.currentPhase === request.fromPhase)
    },
    unacked: (s) => s.doc?.unacked || [],
    drift: (s) => s.doc?.drift || [],
    withheld: (s) => s.doc?.withheld_tasks || 0,
    /** Open blockers, as edges rather than as flags. */
    blockerEdges() {
      const by = Object.fromEntries(this.tasks.map((t) => [t.id, t]))
      const edges = []
      for (const t of this.tasks) {
        for (const b of t.blocked_by || []) {
          const other = by[b] || { id: b, title: '(not in this view)', status: '?' }
          edges.push({ id: t.id, title: t.title, blockedBy: other.id, since: other.title,
                       done: this.terminal.includes(other.status) || other.status === '?' })
        }
      }
      return edges
    },
  },
  actions: {
    async init(api) {
      this.api = api
      const fromUrl = new URLSearchParams(location.search).get('as')
      this.viewer = fromUrl || localStorage.getItem('aim.viewer') || 'human'
      if (fromUrl) localStorage.setItem('aim.viewer', fromUrl)
      await this.load()
    },

    /** Read the record and adopt it as the current one. */
    async load() {
      this.loading = true
      try {
        this.doc = await this.api.state()
        this.viewer = this.doc.viewer
        this.adopt()
        this.error = ''
        this.deferred = false
        this.deferredReason = ''
      } catch (err) {
        this.error = String(err.message || err)
      } finally {
        this.loading = false
      }
    },

    adopt() {
      this.lastDigest = this.doc?.digest || ''
      this.fetchedAt = new Date().toLocaleTimeString()
    },

    /**
     * The record moved. Update, unless updating now would take something away.
     *
     * This is the normal path, not an error path: a peer writes, the digest
     * changes, the board catches up on its own. Only two things veto it -- unsent
     * text in a field, and a reader who has deliberately scrolled away from the
     * top -- and both come back with a visible way to apply the change now.
     */
    async update({ force = false } = {}) {
      const obstruction = force ? null : readingInterrupt()
      if (obstruction) {
        this.deferred = true
        this.deferredReason = obstruction.reason
        return { applied: false, reason: obstruction.reason }
      }
      try {
        const next = await this.api.state()
        const restore = withReadingPosition(() => {
          this.doc = next
          this.viewer = next.viewer
        })
        restore()
        this.deferred = false
        this.deferredReason = ''
        this.adopt()
        this.error = ''
        return { applied: true }
      } catch (err) {
        // A refresh that fails is not a refused write: the board keeps the record
        // it has and the next poll tries again. Saying "the record moved" on a
        // transient fetch failure would be the dashboard inventing an event.
        this.deferred = true
        this.deferredReason = 'the server could not be reached'
        return { applied: false, reason: this.deferredReason }
      }
    },

    /** Cheap: the server answers this from file metadata, not by rendering. */
    async checkDigest() {
      if (document.hidden || !this.api) return
      if (this.deferred) return
      try {
        const { digest } = await this.api.digest()
        if (digest && digest !== this.lastDigest) await this.update()
      } catch { /* a dashboard that cannot reach its server should say so on load, not shout here */ }
    },

    async setViewer(who) {
      this.viewer = who
      localStorage.setItem('aim.viewer', who)
      const url = new URL(location.href)
      url.searchParams.set('as', who)
      history.replaceState(null, '', url)
      await this.load()
    },
  },
})

export { days, isOverdue }
