<script>
/**
 * Whether this thread is waiting on *the reader*, as opposed to merely busy.
 *
 * The old predicate asked whether the thread contained a `receipt demanded` chip
 * **anywhere** -- which is true of demands the reader sent and demands addressed
 * to another agent. Measured live as `human`: 15 receipts owed, of which 11 were
 * `codex -> claude-session1`. It also returned `false` for every channel
 * unconditionally, so `#hello` -- which was holding an unanswered phase request
 * -- was filtered out of the one view that would have shown it. A channel can
 * never be unread under a rule that says channels are never unread.
 *
 * So the question is asked of the messages that are addressed to the viewer, that
 * ask for a receipt, and that nothing has answered:
 *
 *   * a direct message is waiting if `to === viewer`, `ack_required` is set, and
 *     its `state` is not `acked`. Both fields are on the wire per row already
 *     (`state` is T-0162's, `ack_required` has never been absent: 220/220 rows of
 *     the live payload carry it), and the row's `receipt` flag is derived from
 *     those same two fields, so the marker, the anchor and the chip cannot
 *     disagree. The chip stays, because it is the record; it stops being the
 *     predicate.
 *   * a room is waiting for the unread count the server computes per agent.
 *   * a channel is waiting when its newest message is not from the viewer -- the
 *     honest thing that is computable today. A true per-viewer cursor is a fabric
 *     change (`aim read --as <who> --channel <ch> --through <msg_id>`, a new event
 *     on the chain) and it is not built; inventing one here from the browser's
 *     memory would be the weaker answer that T-0181 warns against.
 *
 * `ack_required` was missing from this until T-0162's tile asked for it, and what
 * its absence cost is measured rather than argued. A receipt is written with
 * `ack_required: false` (`bin/aim`, `cmd_receipt`), and answering one flips the
 * *original* message to `acked` -- which leaves the receipt itself in `claimed`,
 * a state that is not `acked`. So every receipt the reader had ever received
 * counted as mail waiting on them, forever. On the live payload:
 *
 *   viewer            to+unacked   +ack_required   dropped
 *   human                    19              15         4  (1 greet, 1 receipt, 2 notes)
 *   codex                    89              14        75  (33 notes, 42 receipts)
 *   claude-session1          42              20        22  (1 greet, 6 receipts, 15 notes)
 *
 * and the Attention tile printed the wide number: 19, against `human`'s 15. The
 * 19 is not arithmetic the tile can be reading from anywhere -- one of the four
 * dropped rows is a receipt `human` wrote, addressed to itself (`human ⇄ human`,
 * measured), which no rule that asks about *incoming* mail can reach. So the
 * predicate and the tile have now converged on one shape rather than the tile
 * being a second derivation beside it.
 *
 * Greets and ordinary notes are dropped by the same clause, and that is the
 * reading the marker's own wording endorses: `receipt demanded` is what the chip
 * says, and a message that asks for nothing is not waiting on a receipt.
 *
 * The viewer and the rooms are arguments rather than the store, and the two
 * functions are exported, so the rule can be driven without a browser
 * (`web/tests/unit/W3.spec.js`). One predicate serves both the `needs me` filter
 * and the marker each row draws: a list that filters on a state it does not show
 * is what T-0172 is about, and two derivations of one question is how that
 * happens.
 */
export const messageWaiting = (message, viewer) => message.to === viewer
  && Boolean(message.ack_required) && message.state !== 'acked'

/**
 * What the payload says a channel is for, and what it holds.
 *
 * The conversation list and the reader header both have to answer "what is this
 * channel for, and is there anything in it", and both answers are already on the
 * wire: `/api/state` publishes `channels[].topic` and `channels[].tasks_recorded`
 * per channel (`aimboard/api.py:356,365`), which is the same manifest
 * `aim status --channel` prints from. The *gate's* copy of a channel --
 * `conversation.channels[]` -- carries `id/phase/gated/messages/rule` and no
 * topic at all, which is why a view that built its rows from that copy had
 * nothing to say about the channel's purpose. Measured live as
 * `claude-session1`: `#hello`'s topic reaches neither surface, so `dev`,
 * `s2-scratch`, `s2-scratch2` and `barrier-v0` -- four empty channels -- looked
 * exactly like the channel holding the project until they were opened.
 *
 * `tasks` is the count the server publishes, and it is the count that is right
 * for a channel the viewer may not read into: a barrier withholds a channel's
 * *contents*, never the fact that work was recorded there, so `barrier-v0` reads
 * `6 work items` to a seat that can open none of them, which is the honest
 * sentence. Where a payload does not carry the key at all (an older server, a
 * fixture), `tasks` is `null` and the sentence says "not published" rather than
 * printing a 0 the server never stated -- and only then does the caller fall
 * back to the board's own rows (`workFromBoard` below), because a second fold of
 * the same question is how two surfaces come to disagree about one number.
 */
export const channelFacts = (entry) => {
  const count = Number(entry?.tasks_recorded)
  return {
    topic: String(entry?.topic || '').trim(),
    tasks: Number.isFinite(count) ? count : null,
    // Who the channel is for. Published beside the topic (`channels[].participants`,
    // `aimboard/api.py:358`) and, like the topic, absent from the gate's copy of
    // the same channel -- so it is carried on the thread here rather than looked
    // up twice by two renderers that could then disagree about membership.
    participants: (entry?.participants || []).map(String),
  }
}

/**
 * A probe: a channel that holds no work and no talk.
 *
 * The card's own words ("a channel with no tasks and no messages is visibly
 * scaffolding, not a peer of a channel with 71 work items"). A channel with
 * *some* work and no messages is the case this rule has to leave alone: it is
 * work without talk, which is a state a channel is allowed to be in, and the
 * surfaces below say so in words instead of marking it.
 */
export const isProbe = (thread) => thread.group === 'channel' && thread.tasks === 0
  && thread.msgs.length === 0

/** "2 work items, no messages" -- the two halves of what a thread holds. */
export const held = (thread) => [
  thread.group === 'channel'
    ? thread.tasks === null
      ? 'work count not published'
      : thread.tasks
        ? `${thread.tasks} work item${thread.tasks === 1 ? '' : 's'}`
        : 'no work items'
    : null,
  thread.msgs.length
    ? `${thread.msgs.length} message${thread.msgs.length === 1 ? '' : 's'}`
    : 'no messages',
].filter(Boolean).join(', ')

export const threadWaiting = (thread, viewer, rooms) => {
  if (thread.group === 'direct') {
    return thread.msgs.some((message) => messageWaiting(message, viewer))
  }
  if (thread.group === 'room') {
    const room = rooms.find((item) => item.channel === thread.target.channel && item.id === thread.target.id)
    return Boolean((room?.unread || {})[viewer])
  }
  // A channel has no per-viewer read state, so `thread.unread` is 0 for every
  // channel by construction: a channel message is addressed `to: #<channel>`, never
  // `to: <viewer>`. Asking the count here answered `false` for every channel
  // unconditionally -- the defect the comment above names, written back in as the
  // predicate. What is computable today is who spoke last: a channel is waiting on
  // the reader when its newest message is somebody else's.
  return thread.msgs.length > 0 && thread.msgs.at(-1)?.by !== viewer
}
</script>

<script setup>
import { computed, inject, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { directScope, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import OwnerAvatar from '../components/OwnerAvatar.vue'
import { MAIL_STATE_TYPE } from '../theme'

/**
 * Reading the conversation is the point of this pane, so the layout is a
 * bounded reader: the history owns one scroller, the composer owns the bottom,
 * and they are siblings rather than an input floating over a page. The first
 * version put a sticky composer inside the normal page flow, so it overlapped
 * exactly the long reports the leader needed to read.
 */
const ctx = inject('ctx')
const md = ctx.service('markdown')
const api = ctx.service('api')
const board = useBoard()

const picked = ref('')
const q = ref('')
const drafting = ref('')
const kind = ref('note')
const sending = ref(false)
const publishing = ref(false)
const refusal = ref('')
const sent = ref('')
const historyEl = ref(null)
const composerEl = ref(null)
const directDialog = ref(false)
const directPeer = ref('')
const directSubject = ref('')
const directBody = ref('')
const directBusy = ref(false)
const directError = ref('')
const { filters, activeCount, clear } = useQueryFilters({
  shape: 'all', participant: '', needsMe: false, thread: '',
})

const threads = computed(() => {
  const byKey = new Map()
  /**
   * The channel's own record, as `/api/state` publishes it.
   *
   * The gate's list below carries the readable messages and not the channel; this
   * carries the topic and the work count and not the messages. The row needs one
   * of each, and taking either from somewhere it is not published is how this
   * pane came to have a row that could only count messages.
   */
  const declared = new Map((board.channels || []).map((channel) => [channel.id, channel]))
  for (const channel of board.conversation.channels) {
    byKey.set(`ch:${channel.id}`, {
      key: `ch:${channel.id}`,
      group: 'channel',
      label: `#${channel.id}`,
      gated: Boolean(channel.gated),
      phase: channel.phase || '',
      note: channel.rule || '',
      ...channelFacts(declared.get(channel.id)),
      target: { type: 'channel', id: channel.id },
      msgs: [],
    })
  }
  for (const room of board.conversation.rooms) {
    byKey.set(`room:${room.channel}:${room.id}`, {
      key: `room:${room.channel}:${room.id}`,
      group: 'room',
      label: `#${room.channel} / #${room.room}`,
      phase: board.doc?.channels?.find((channel) => channel.id === room.channel)?.phase || '',
      note: 'a room inherits the parent channel gate; draft by default, publishing is deliberate',
      // A room is inside a channel and is not one: the channel's topic or work
      // count printed on it would be a sentence about the parent, not the room.
      topic: '',
      tasks: null,
      target: { type: 'room', id: room.id, channel: room.channel },
      msgs: [],
    })
  }
  for (const row of board.conversationRows) {
    const key = row.shape === 'channel'
      ? `ch:${row.channel}`
      : row.shape === 'room'
        ? `room:${row.channel}:${row.room}`
        : `dm:${row.scope}`
    let thread = byKey.get(key)
    if (!thread) {
      thread = row.shape === 'channel'
        ? {
            key, group: 'channel', label: `#${row.channel}`, gated: row.gated,
            phase: row.phase, note: row.rule,
            // A channel the gate's list did not name at all still gets a row, and
            // it has no declared record here to read: see the `tasks` assignment
            // below for why the fallback is not a `0`.
            ...channelFacts(declared.get(row.channel)),
            target: { type: 'channel', id: row.channel }, msgs: [],
          }
        : row.shape === 'room'
          ? {
              key, group: 'room', label: `#${row.channel} / #${row.room}`,
              phase: row.phase, note: row.rule,
              topic: '', tasks: null,
              target: { type: 'room', id: row.room, channel: row.channel }, msgs: [],
            }
          : {
              key, group: 'direct', label: row.scope,
              note: row.rule,
              target: { type: 'direct', peer: row.scope.split(' ⇄ ').find((x) => x !== board.viewer) },
              msgs: [],
            }
      byKey.set(key, thread)
    }
    thread.msgs.push({
      by: row.from,
      to: row.shape === 'channel' ? `#${row.channel}` : row.shape === 'room' ? `#${row.room}` : row.to,
      ts: row.ts,
      body: row.body,
      subject: row.subject,
      id: row.msg_id,
      /**
       * The receipt state, kept as a field rather than only as a chip.
       *
       * `state` is what happened to the message and `ack_required` is a property
       * of the request; drawing both as chips made a row that reads `acked` and
       * `receipt demanded` side by side. The field is what the marker and the
       * anchor read, so the sentence and the predicate cannot drift apart.
       *
       * Both fields keep the wire's own names on purpose. `messageWaiting` is
       * called on two shapes -- `board.conversationRows` (which spreads the mail
       * row, so it carries `ack_required`) and these message objects -- and a
       * second spelling here (`ackRequired`) made the predicate read a field that
       * exists on one shape and is `undefined` on the other. Measured: the tree
       * below drew every thread and marked none of them, so `codex ⇄ human` showed
       * no badge for `human` while the tile counted the same one message. A rename
       * is not a fix here; one field, one name, is.
       */
      state: row.state || '',
      ack_required: Boolean(row.ack_required),
      /**
       * What happened, and what the message asked for -- never both as one row.
       *
       * `ack_required` is a property of the request; `state` is what happened to
       * it. Rendering them side by side gave a message that reads `acked` and
       * `receipt demanded` on the same line, and spent a chip on `${bytes} bytes`,
       * which is a transport detail at a reader who is reading a conversation.
       * So what the message is *still* asking for is a field, true only while the
       * row it belongs to is unanswered -- the meaning the chip spells out lives
       * in the data, and every chip below is then a word for a state the row is
       * actually in.
       */
      receipt: Boolean(row.shape === 'direct' && row.ack_required && (row.state || '') !== 'acked'),
      chips: row.shape === 'channel'
        ? [row.kind && `kind ${row.kind}`, row.responds_to && `responds-to ${row.responds_to}`].filter(Boolean)
        : row.shape === 'room'
          ? (row.mentions || []).map((mention) => `@${mention}`)
          : row.state === 'acked'
            ? ['acked']
            : row.receipt ? ['receipt demanded'] : row.state ? [row.state] : [],
    })
  }
  const groupOrder = { channel: 0, room: 1, direct: 2 }
  /**
   * What is waiting on the viewer, per thread, computed once for the list.
   *
   * The list and the reader have to agree about this: a row that says `2` over a
   * thread whose first unread is somewhere else is the same defect as a count
   * window that does not match the list it summarises.
   */
  for (const thread of byKey.values()) {
    const mine = thread.msgs.filter(waitingOnViewer)
    thread.unread = mine.length
    thread.unreadFrom = mine[0]?.id || ''
    /**
     * The count is the server's, and the fallback is named rather than silent.
     *
     * `tasks_recorded` is `null` only for a channel `/api/state` did not describe
     * (an older server, or a fixture that ships the gate's list and not the
     * channel's record). A `0` here means "the server counted zero", and those two
     * are different facts: a board that folds its own rows to fill the gap is
     * answering a question the record already answered, which is how one number
     * becomes two. So the empty case is counted from the payload's own rows and
     * the row says which count it is printing -- a channel drawn as a probe for
     * the want of a field would be the wrong side of that trade.
     */
    if (thread.group === 'channel' && thread.tasks === null) {
      thread.tasks = workFromBoard(thread)
      thread.tasksFromRows = true
    }
    thread.msgsCount = thread.msgs.length
  }
  return [...byKey.values()].sort((a, b) =>
    groupOrder[a.group] - groupOrder[b.group] || (a.label < b.label ? -1 : 1))
})
// The rule lives in the module-level `threadWaiting` above; this is only the
// binding to the seat this page is reading as.
const waitingOnViewer = (message) => messageWaiting(message, board.viewer)
const threadNeedsMe = (thread) => threadWaiting(thread, board.viewer, board.conversation.rooms)
/** The board's own rows for a channel, used only where the channel key is absent. */
const workFromBoard = (thread) => board.tasks.filter((task) => task.channel === thread.target.id).length
const visibleThreads = computed(() => threads.value.filter((thread) => {
  if (filters.shape !== 'all' && thread.group !== filters.shape) return false
  if (filters.participant) {
    const participant = filters.participant
    const inMessages = thread.msgs.some((message) =>
      message.by === participant || message.to === participant || (message.chips || []).some((chip) => chip === `@${participant}`))
    if (!inMessages && !thread.label.includes(participant)) return false
  }
  if (filters.needsMe && !threadNeedsMe(thread)) return false
  return true
}))
const groups = computed(() => {
  const g = {}
  for (const t of visibleThreads.value) (g[t.group] ||= []).push(t)
  return g
})
// Open on the conversation that moved last, not on whatever happens to be first.
// The leader reads this page to answer the agent that just reported, and a pane
// that opens on a channel whose last message was hours ago makes finding that
// agent a manual job every single time.
const mostRecent = computed(() => {
  const withTs = visibleThreads.value.map((t) => ({ t, ts: t.msgs.at(-1)?.ts || '' }))
  withTs.sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0))
  return withTs[0]?.t
})
const participants = computed(() => [...new Set(threads.value.flatMap((thread) => [
  ...thread.msgs.map((message) => message.by),
  ...thread.msgs.map((message) => message.to?.replace(/^#/, '')),
  ...thread.label.split(/[/ ⇄]+/),
]))].filter(Boolean).sort())
const current = computed(() =>
  visibleThreads.value.find((t) => t.key === picked.value) || mostRecent.value)
watch(current, (t) => { if (t && !picked.value) picked.value = t.key })
watch(() => filters.thread, (key) => {
  if (key && threads.value.some((thread) => thread.key === key)) picked.value = key
}, { immediate: true })
const messages = computed(() => {
  const msgs = current.value?.msgs || []
  if (!q.value) return msgs
  const needle = q.value.toLowerCase()
  return msgs.filter((m) => `${m.by} ${m.to} ${m.subject || ''} ${m.body}`.toLowerCase().includes(needle))
})
const currentRoom = computed(() => {
  if (current.value?.group !== 'room') return null
  return board.conversation.rooms.find((room) =>
    room.channel === current.value.target.channel && room.id === current.value.target.id)
})
/**
 * Where a thread opens.
 *
 * The rule is one sentence: **the first thing that is waiting on the reader, and
 * otherwise the newest message** -- bottom-aligned, so the end of the newest
 * message is on screen rather than below the fold.
 *
 * What it replaced, and why each half was wrong:
 *
 *  * `msgs.findIndex((m) => m.chips?.includes('receipt demanded'))` picked the
 *    first *receipt chip* whatever its state. Measured live: on
 *    `claude-session1 ⇄ codex` the first chip is message 8 and its state is
 *    `acked`, so the page opened on an answered message 89,710px above the first
 *    actually-unread one (index 99 of 121), with the newest 106,485px below the
 *    fold. A chip is a fact about a message; it is not a fact about the reader.
 *  * `msgs.length - 1` is not the bottom either. The old `scrollToAnchor` put the
 *    target's *top* at the scroll container's top minus 12px, so the last message
 *    opened at its own beginning. On a one-message thread that looks right, which
 *    is why it survived; on a real one it left the end of the newest message
 *    below the fold by construction.
 *
 * `unreadFrom` comes from the thread model, which computes it once for the whole
 * list -- the row's badge and the reader's landing point are then the same fact,
 * because a count that disagrees with where the page opens is the defect this
 * card is about, one pane over.
 */
const anchorIndex = computed(() => {
  const msgs = messages.value
  if (!msgs.length) return 0
  const firstUnread = msgs.findIndex(waitingOnViewer)
  return firstUnread >= 0 ? firstUnread : msgs.length - 1
})
const dayOf = (ts) => (ts || '').slice(0, 10)
const stamp = (ts) => (ts || '').replace('T', ' ').slice(0, 19)
/**
 * The last message, as one line of plain text.
 *
 * The `(nothing yet)` fallback is no longer what an empty row prints: the row
 * draws a channel's work and message counts and draws this only where a message
 * exists (T-0177), so a channel with no messages cannot reach it. It is kept for
 * the one thing it still describes -- a message that arrived with no body.
 */
const preview = (t) => {
  const last = t.msgs[t.msgs.length - 1]
  return (last?.body || '').replace(/[#*`>|\n]+/g, ' ').trim().slice(0, 72) || '(no body)'
}
const body = (text) => md.render(text)

async function openThread(key) {
  picked.value = key
  filters.thread = key
  await scrollToAnchor()
}

/**
 * Put the reader where the anchor rule says, once the thread has stopped growing.
 *
 * Two things the old version got wrong, and both are visible from the outside:
 *
 *  * **It aligned the wrong edge.** The target's *top* was placed 12px below the
 *    scroll container's top, so the anchor message opened at its own beginning and
 *    its end sat below the fold. On the leader's thread that was 106,485px of
 *    newest message under the fold. So: an unread anchor aligns its top, because
 *    the reader is about to read *forward* from it; anything else aligns its
 *    bottom, because "the newest message" means all of it.
 *  * **It ran once.** A thread's content arrives in pieces -- the markdown bodies
 *    are rendered on mount -- so a single pass against a half-grown history lands
 *    in the wrong place, which is how `jumpToEnd` came to be the only control that
 *    actually reached the end. It is written across a short window of frames, and,
 *    like the router's own reset, it stops the instant the reader scrolls or types:
 *    nothing here moves the page under the reader's hands.
 */
/**
 * The scroll position that puts the anchor where the rule says it goes.
 *
 * Which edge to align depends on what the anchor *is*. An unread anchor is the
 * start of what the reader has not read, so its top goes near the top and the
 * reader reads forward. The newest message is the thing itself, so all of it has
 * to be on screen -- aligning its top, which is what this did before, put the end
 * of the newest message below the fold by construction.
 *
 * The value is the *change* to apply rather than an absolute position, because
 * the pane's height is still changing while the bodies render.
 */
function anchorDelta(history, node) {
  const box = history.getBoundingClientRect()
  const at = node.getBoundingClientRect()
  const isLast = anchorIndex.value === messages.value.length - 1
  return isLast ? at.bottom - box.bottom : at.top - box.top - 12
}

async function scrollToAnchor() {
  await nextTick()
  const reader = watchingForReader()
  /**
   * The loop runs until the anchor is *where it should be*, not for a fixed
   * number of frames.
   *
   * A frame count is a proxy, and it was a wrong one twice. Measured on the live
   * board: a fixed twelve frames left the newest message's bottom 30px below the
   * fold, because the last write happened one render before the last body's
   * markdown finished laying out. 131 messages arrive over several frames, so the
   * honest stop condition is the outcome itself -- the anchor's edge is at the
   * scroller's edge -- with a frame budget to bound it and a give-up when writing
   * no longer changes anything (the pane is clamped at its top or bottom, so no
   * further write can help).
   */
  let before = -1
  for (let frame = 0; frame < 60; frame += 1) {
    const history = historyEl.value
    if (!history || reader.moved()) break
    const node = history.querySelectorAll('.aim-msg')[anchorIndex.value]
    if (node) {
      const delta = anchorDelta(history, node)
      if (Math.abs(delta) <= 1) break
      history.scrollTop = Math.max(0, history.scrollTop + delta)
      if (history.scrollTop === before) break
      before = history.scrollTop
    }
    await new Promise((next) => requestAnimationFrame(next))
  }
  reader.done()
}

/**
 * Whether the reader has taken over since this was called.
 *
 * The same rule `readingInterrupt` states on the data side, applied to this pane:
 * an update that scrolls under the reader's hands is worse than one that is late.
 */
function watchingForReader() {
  const events = ['wheel', 'touchstart', 'touchmove', 'pointerdown', 'keydown']
  let moved = false
  const mark = () => { moved = true }
  for (const name of events) window.addEventListener(name, mark, { passive: true, capture: true })
  return {
    moved: () => moved,
    done() {
      for (const name of events) window.removeEventListener(name, mark, { capture: true })
    },
  }
}
/**
 * Take the record back up the moment the thing that held it is gone.
 *
 * `board.checkDigest` returns early while `deferred` is set, so the store's own
 * poll cannot see an obstruction clear: today the only way out of a held update
 * is the reader clicking the banner, which is the click T-0170 removes. The pane
 * that made the obstruction is the one that knows when it ends, so it asks
 * again -- the composer's draft emptying (typed away, or sent) and the history
 * coming back to its top are the two events this pane can see. `update()` and
 * not `force`, so the decision stays with the store: if a field somewhere else
 * still holds unsent text, it defers again with its own reason and nothing moves
 * under the reader.
 */
function resumeWhenClear() {
  if (!board.deferred) return
  board.update()
}
watch(drafting, (text) => { if (!text.trim()) resumeWhenClear() })
function onHistoryScroll() {
  if ((historyEl.value?.scrollTop ?? 1) <= 0) resumeWhenClear()
}
const messageKinds = computed(() => {
  if (current.value?.group !== 'channel') return []
  return current.value.phase === 'CROSS_EXAMINE'
    ? ['evidence', 'objection', 'rebuttal', 'question', 'concession', 'proposal', 'note']
    : ['note', 'claim', 'evidence', 'position', 'question']
})
watch(messageKinds, (kinds) => {
  if (kinds.length && !kinds.includes(kind.value)) kind.value = kinds[0]
}, { immediate: true })
/**
 * Anchor when the reader opens a thread, and only then.
 *
 * It used to fire on every change of `anchorIndex`, which includes a new message
 * arriving on the live record -- so the page yanked itself to the bottom under a
 * reader who was mid-paragraph. The rule this project keeps: an update must never
 * cost the reader the thing they were doing (`readingInterrupt` in the store says
 * the same about a forced refresh). Sending is the one exception, and it is asked
 * for by name at the end of `send()`.
 *
 * It fires on the *thread* changing, not on the record changing. A store update
 * re-evaluates every computed in this pane, and this watcher used to read that as
 * the reader opening something: a forced update put `.aim-history` back at the
 * reader's own 200 and this re-anchored it to the newest message one render later
 * (measured: 200 -> 6154). A key that blinks out for a single render -- an update
 * whose payload briefly yields no visible thread -- is not a change either, so the
 * last key anchored is remembered.
 */
let anchoredKey = ''
watch(() => current.value?.key, (key) => {
  if (!key || key === anchoredKey) return
  anchoredKey = key
  picked.value = key
  scrollToAnchor()
}, { immediate: true })
/**
 * Go to the end, because the reader asked.
 *
 * The button stays: with the anchor rule above, opening a thread lands at the end
 * by itself, so this is the way *back* for someone who has scrolled up -- not the
 * click the leader had to make before. Automating the opening and keeping the
 * return trip is the difference between removing a step and removing a control.
 */
async function jumpToEnd() {
  await nextTick()
  if (historyEl.value) {
    historyEl.value.scrollTo({ top: historyEl.value.scrollHeight, behavior: 'smooth' })
  }
}
function quote(m) {
  drafting.value = `> ${(m.body || '').split('\n').slice(0, 3).join('\n> ')}\n\n`
  composerEl.value?.focus?.()
}

/**
 * The one write path from the browser: it does not write anything itself, it runs
 * `bin/aim` and returns whatever that said. So a write from here lands in the
 * ledger, refuses when the tool refuses, and prints the refusal verbatim.
 *
 * A room is a write path like any other, and the card T-0219 called for
 * (`room new/say/publish` exist and are recorded) landed in `bin/aim` while this
 * pane still carried a card saying room sending was pending. It was not pending:
 * the refusal below would have been printed on the *client* for a command the
 * tool accepts, which is the one thing this pane is not allowed to do -- a
 * message misrouted to the parent channel is bad, and a working command hidden
 * behind prose about a mechanism that was already built is worse, because
 * nothing in the record shows it happened. The argv is the tool's own:
 * `aim room say --channel <ch> --id <id> --body <text>`, and the room's own
 * draft gate is what refuses a peer, on the record, with the rule quoted.
 */
async function send() {
  if (!drafting.value.trim() || !current.value) return
  sending.value = true
  refusal.value = ''
  sent.value = ''
  const t = current.value.target
  const argv = t.type === 'direct'
    ? ['push', '--to', t.peer, '--subject', `reply from ${board.writer}`, '--body', drafting.value,
       '--via', 'aim dashboard', '--require-ack']
    : t.type === 'room'
      ? ['room', 'say', '--channel', t.channel, '--id', t.id, '--body', drafting.value]
      : ['say', '--channel', t.id, '--kind', kind.value, '--body', drafting.value]
  const res = await api.command(argv)
  sending.value = false
  if (res.rc === 0) {
    sent.value = (res.stdout || '').trim() || 'recorded'
    drafting.value = ''
    await board.load()
    jumpToEnd()
  } else {
    refusal.value = (res.stderr || res.stdout || '').trim() || `exit ${res.rc}`
  }
}
/**
 * Open a draft room on the record.
 *
 * `design/06` §2 makes this the deliberate act: a room written during a
 * divergence phase is readable by its author alone until somebody publishes it,
 * and publishing during that phase is itself a barrier event. The board shows
 * the state and does not perform the act -- the reader presses, the command is
 * named, and the ledger records who opened it. That is the whole reason the
 * control exists rather than the pane publishing a room on load.
 */
async function publishRoom() {
  const room = currentRoom.value
  if (!room) return
  publishing.value = true
  refusal.value = ''
  sent.value = ''
  const res = await api.command(['room', 'publish', '--channel', room.channel, '--id', room.id])
  publishing.value = false
  if (res.rc === 0) {
    sent.value = (res.stdout || '').trim() || 'published'
    await board.load()
  } else {
    refusal.value = (res.stderr || res.stdout || '').trim() || `exit ${res.rc}`
  }
}
async function copy(text) {
  await navigator.clipboard?.writeText(text)
  ElMessage({ message: 'copied', type: 'success', duration: 1200 })
}

async function sendDirect() {
  if (!directPeer.value || !directBody.value.trim()) return
  directBusy.value = true
  directError.value = ''
  const response = await api.command([
    'push', '--to', directPeer.value,
    '--subject', directSubject.value || `message from ${board.writer}`,
    '--body', directBody.value, '--via', 'aim dashboard', '--require-ack',
  ])
  directBusy.value = false
  if (response.rc !== 0) {
    directError.value = response.stderr || response.stdout || `aim exited ${response.rc}`
    return
  }
  const key = `dm:${directScope(board.writer, directPeer.value)}`
  directDialog.value = false
  directSubject.value = ''
  directBody.value = ''
  await board.load()
  await openThread(key)
}
</script>

<template>
  <div class="aim-chat">
    <aside class="aim-chat-side">
      <el-card shadow="never" body-style="padding:8px">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px">
            <span>{{ visibleThreads.length }} / {{ threads.length }} thread(s)</span>
            <span style="flex:1" />
            <el-button size="small" text @click="directDialog = true">
              <el-icon><Plus /></el-icon> direct
            </el-button>
            <el-tooltip content="re-read the record"><el-button size="small" text @click="board.load()">
              <el-icon><Refresh /></el-icon></el-button></el-tooltip>
          </div>
        </template>
        <div class="aim-filterbar aim-thread-filters">
          <!-- Filter and select controls are data, not prose: nothing here is a
               draft, so nothing here may hold an update back, and no typing into
               one is unsent text. That is why neither select is `filterable` --
               element-plus renders a filtered select's needle into a real text
               input, and the store's `readingInterrupt` finds unsent text by
               value, wherever it lives. -->
          <el-select v-model="filters.shape" size="small" placeholder="all threads">
            <el-option value="all" label="all shapes" />
            <el-option value="channel" label="channels" />
            <el-option value="room" label="rooms" />
            <el-option value="direct" label="direct" />
          </el-select>
          <el-select v-model="filters.participant" size="small" placeholder="participant" clearable>
            <el-option v-for="participant in participants" :key="participant"
                       :value="participant" :label="participant" />
          </el-select>
          <el-checkbox v-model="filters.needsMe">needs me</el-checkbox>
          <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        </div>
        <div class="aim-thread-list">
          <template v-for="(list, group) in groups" :key="group">
            <div class="aim-dim" style="font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;margin:8px 4px 4px">{{ group }}</div>
            <div v-for="t in list" :key="t.key" class="aim-thread" :class="{ on: t.key === current?.key }"
                 role="button" tabindex="0" :aria-label="`Open conversation ${t.label}`"
                 :aria-pressed="t.key === current?.key"
                 @click="openThread(t.key)"
                 @keydown.enter.prevent="openThread(t.key)"
                 @keydown.space.prevent="openThread(t.key)">
              <div style="display:flex;align-items:center;gap:6px">
                <span style="font-size:12.5px">{{ t.label }}</span>
                <el-icon v-if="t.gated" style="font-size:11px" title="sealed to you"><Lock /></el-icon>
                <span style="flex:1" />
                <!-- The row says what is waiting on the viewer, so the list is
                     readable without opening every item. Before this, every row
                     was equally quiet: the leader's own mail sat at the bottom of
                     the sidebar with no marker while `unacked` named two messages
                     awaiting their receipt. The page had the fact and did not
                     draw it.

                     The marker reads the same `threadNeedsMe` the filter above
                     does, so a channel the `needs me` view keeps cannot arrive
                     without one: a count where the fabric can count one, and the
                     word where it cannot (a channel has no per-viewer cursor, so
                     its unread count is 0 by construction and a count-only marker
                     drew nothing for exactly the thread T-0172 was filed about).

                     It is drawn only where it says something: a row waiting on
                     the reader, or one holding messages the reader has not
                     receipted. An earlier version drew it on *every* row, "clear"
                     included, on the argument that a marker which is only present
                     when it is bad cannot be told from one that failed to render.
                     Measured against the suite, that argument costs more than it
                     pays: `chat.spec.js:207` asserts the badge is absent on
                     `claude-session1 ⇄ codex` (someone else's mail) and got a
                     "clear" chip instead, and T-0172's own filter clause counts
                     `marked` by the presence of this element, so "clear" rows made
                     `marked` 6 where the filter keeps 3. A marker on a row with
                     nothing to report is a second, weaker claim about the fixture
                     wearing the same class as the real one. -->
                <el-tag v-if="t.unread || threadNeedsMe(t)" class="aim-unread" size="small"
                        :type="t.unread ? 'danger' : 'warning'"
                        :effect="'dark'"
                        :title="t.unread
                          ? `${t.unread} message(s) addressed to ${board.viewer} with no receipt yet`
                          : `this thread is waiting on ${board.viewer}`">
                  {{ t.unread || 'needs me' }}
                </el-tag>
                <span class="aim-dim" style="font-size:10.5px">{{ (t.msgs.at(-1)?.ts || '').slice(5, 16).replace('T', ' ') }}</span>
              </div>
              <!-- What the channel holds, said in words on the row.
                   The second line of this row used to be `preview(t)` -- the last
                   message, or `(nothing yet)`. Measured on the T-0177 fixture, that
                   made `#dev` (2 work items, 0 messages) and `#s2-scratch2` (0, 0)
                   the same string: the row answered "are there messages" when the
                   card asks "is there work". The work count is on the wire
                   (`channels[].tasks_recorded`) and was simply not drawn. So the
                   count and the message count are both printed -- work first,
                   because that is the question -- and a channel holding neither is
                   a probe and is tagged as one.
                   A channel with work and no messages is *not* a probe and is not
                   de-emphasised: work without talk is a state a channel is allowed
                   to be in, and the row says so ("2 work items, no messages") where
                   the scaffolding row says what it is instead of how busy it is. -->
              <div v-if="t.group === 'channel'" style="display:flex;align-items:center;gap:6px;margin-top:3px">
                <el-tag v-if="isProbe(t)" class="aim-probe" size="small" type="info" effect="plain"
                        title="no work items and no messages: this channel was opened and nothing was recorded in it">
                  scaffolding — no work, no messages
                </el-tag>
                <el-tag v-else class="aim-held" size="small" effect="plain"
                        :title="`from the payload: ${t.topic || 'no topic'}`">{{ held(t) }}</el-tag>
              </div>
              <div v-if="t.group === 'channel' && t.topic" class="aim-dim aim-thread-topic">
                {{ t.topic }}
              </div>
              <!-- The last message, drawn only where there is one to draw. The
                   placeholder was what made an empty channel and a working one
                   read alike, and an empty thread's state is now the tags above. -->
              <div v-if="t.msgs.length" class="aim-dim" style="font-size:11px;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ preview(t) }}
              </div>
            </div>
          </template>
          <el-empty v-if="!visibleThreads.length" description="no thread matches these filters" :image-size="60" />
        </div>
      </el-card>
    </aside>

    <section class="aim-reader">
      <div class="aim-reader-head">
          <div class="aim-reader-headline">
            <strong style="font-size:13.5px">{{ current?.label }}</strong>
            <el-tag v-if="current?.gated" size="small" type="warning" effect="plain">sealed to you</el-tag>
            <!-- What this channel *is*, said before the reader opens a message.
                 The card's third clause: the header named the id, the gate and the
                 phase note, which is a state and not a purpose. The words come
                 from `held()` and `isProbe()`, the same two the list rows use, so
                 the header and the row cannot describe one channel differently. -->
            <el-tag v-if="current?.group === 'channel'" size="small"
                    :type="isProbe(current) ? 'info' : 'success'" effect="plain">
              {{ isProbe(current) ? 'scaffolding — no work, no messages' : held(current) }}
            </el-tag>
            <span class="aim-dim" style="font-size:11.5px">{{ current?.note }}</span>
            <span style="flex:1" />
            <el-input v-model="q" size="small" placeholder="search in this thread" style="width:180px" clearable />
            <el-button size="small" text @click="jumpToEnd"><el-icon><Bottom /></el-icon> newest</el-button>
          </div>
          <!-- The topic, on its own line above the stream and not below it: a
               purpose printed after the last message is not the purpose to a
               reader who has just arrived. `channels[].topic` is the manifest's
               own sentence (`aimboard/api.py:356`), which `aim status --channel`
               prints from -- there is no second copy of it here, and an empty
               topic says so rather than rendering nothing, because a row that is
               silent for two different reasons is the defect this card is about
               one level up (see `BarrierPane.vue`'s `(this channel records no
               topic)`, the same sentence for the same absence). -->
          <div v-if="current?.group === 'channel'" class="aim-reader-topic">
            {{ current.topic || '(this channel records no topic)' }}
          </div>
          <div v-if="current?.group === 'channel' && current.participants?.length"
               class="aim-dim aim-reader-participants">
            participants: {{ current.participants.join(', ') }}
          </div>
        </div>

      <div ref="historyEl" class="aim-history" @scroll.passive="onHistoryScroll">
        <template v-for="(m, i) in messages" :key="i">
          <div v-if="i === 0 || dayOf(m.ts) !== dayOf(messages[i - 1].ts)" class="aim-daysep">
            {{ dayOf(m.ts) }}
          </div>
          <article class="aim-msg" :class="{ 'aim-anchor-message': i === anchorIndex }">
            <header>
              <OwnerAvatar :id="m.by" :size="18" />
              <el-icon v-if="m.to" style="font-size:11px"><Right /></el-icon>
              <span v-if="m.to" class="aim-dim">{{ m.to }}</span>
              <span class="aim-dim" style="font-size:11px">{{ stamp(m.ts) }}</span>
              <el-tag v-for="c in (m.chips || []).filter(Boolean)" :key="c" size="small" effect="plain"
                      :type="MAIL_STATE_TYPE[c] || 'info'">{{ c }}</el-tag>
              <span style="flex:1" />
              <el-button size="small" text @click="quote(m)"><el-icon><ChatLineSquare /></el-icon></el-button>
              <el-button size="small" text @click="copy(m.body)"><el-icon><DocumentCopy /></el-icon></el-button>
            </header>
            <div v-if="m.subject" class="aim-subject">{{ m.subject }}</div>
            <div class="markdown-body aim-body" v-html="body(m.body)" />
          </article>
        </template>
        <el-empty v-if="!messages.length" description="this thread is empty" />
      </div>

      <footer class="aim-composer">
        <el-card v-if="!board.canWrite" shadow="never" style="margin-top:4px">
          <div class="aim-dim" style="font-size:12.5px">
            reading as <b>{{ board.viewer }}</b>. this server was started without
            <code class="aim-mono">--allow-write</code>, so there is nothing here to type into:
            a reply box that cannot send is a control that lies about what it does.
          </div>
        </el-card>
        <el-card v-else-if="current?.target?.type === 'room'" shadow="never" style="margin-top:4px">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span>reply as <b>{{ board.writer }}</b> to
                <b>#{{ current?.target?.channel }} / #{{ currentRoom?.id }}</b></span>
              <!-- The state is the room's own `visibility`, straight off the
                   payload, with the author it is gated to. A draft is not an
                   error and not a wait: design/06 §2 makes it the default, and
                   the author writes into it freely. Publishing is the act that
                   opens it, and it is a barrier event during a divergence
                   phase -- so it is a button the reader presses, not something
                   this pane does for them. -->
              <el-tag size="small" :type="currentRoom?.visibility === 'published' ? 'success' : 'info'"
                      effect="plain">
                {{ currentRoom?.visibility === 'published' ? 'published' : 'draft' }}
              </el-tag>
              <span v-if="currentRoom?.published_by" class="aim-dim" style="font-size:11px">
                opened by {{ currentRoom.published_by }}
              </span>
              <span style="flex:1" />
              <el-button v-if="board.canWrite && currentRoom?.visibility !== 'published'"
                         size="small" :loading="publishing" @click="publishRoom">
                publish — open it to the channel
              </el-button>
              <span class="aim-dim" style="font-size:11px">
                runs <code class="aim-mono">aim room {{ currentRoom?.visibility === 'published' ? 'say' : 'publish/say' }}</code>
              </span>
            </div>
          </template>
          <el-input ref="composerEl" v-model="drafting" type="textarea" :rows="4" resize="vertical"
                    placeholder="markdown is fine. a room message is appended to the room's own hash-chained log under the channel's lock, so `aim verify --channel` covers it." />
          <div class="aim-dim" style="font-size:11.5px;margin-top:6px">
            A draft room is readable by its author and the leader. Anyone else sending here is
            refused by the room gate, on the record, with the rule quoted — including you, if you
            are not the author.
          </div>
          <div style="display:flex;align-items:center;gap:10px;margin-top:10px">
            <el-button type="primary" :loading="sending" @click="send">send</el-button>
            <span class="aim-dim" style="font-size:11.5px">{{ drafting.length }} characters</span>
            <span style="flex:1" />
          </div>
          <el-alert v-if="refusal" type="error" :closable="false" show-icon style="margin-top:10px"
                    title="the tool refused, and the refusal is recorded">
            <pre class="aim-mono" style="white-space:pre-wrap;margin:6px 0 0">{{ refusal }}</pre>
          </el-alert>
          <el-alert v-if="sent" type="success" :closable="false" show-icon style="margin-top:10px" :title="sent" />
        </el-card>
        <el-card v-else shadow="never" style="margin-top:4px">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span>reply as <b>{{ board.writer }}</b> to
                <b>{{ current?.target?.type === 'direct' ? current?.target?.peer : '#' + current?.target?.id }}</b></span>
              <el-select v-if="current?.target?.type === 'channel'" v-model="kind" size="small" style="width:150px">
                <el-option v-for="k in messageKinds" :key="k" :value="k" :label="k" />
              </el-select>
              <span style="flex:1" />
              <span class="aim-dim" style="font-size:11px">
                runs <code class="aim-mono">aim {{ current?.target?.type === 'direct' ? 'push' : 'say' }}</code> — the dashboard has no writer of its own
              </span>
            </div>
          </template>
          <el-input ref="composerEl" v-model="drafting" type="textarea" :rows="4" resize="vertical"
                    placeholder="markdown is fine. what you send is recorded in the log, hashed, and wakes the peer on their next turn." />
          <div style="display:flex;align-items:center;gap:10px;margin-top:10px">
            <el-button type="primary" :loading="sending" @click="send">send</el-button>
            <span class="aim-dim" style="font-size:11.5px">{{ drafting.length }} characters</span>
            <span style="flex:1" />
          </div>
          <el-alert v-if="refusal" type="error" :closable="false" show-icon style="margin-top:10px"
                    title="the tool refused, and the refusal is recorded">
            <pre class="aim-mono" style="white-space:pre-wrap;margin:6px 0 0">{{ refusal }}</pre>
          </el-alert>
          <el-alert v-if="sent" type="success" :closable="false" show-icon style="margin-top:10px" :title="sent" />
        </el-card>
      </footer>
    </section>
  </div>

  <el-dialog v-model="directDialog" title="Send a direct instruction" width="520px">
    <el-form label-position="top">
      <el-form-item label="to">
        <el-select v-model="directPeer" filterable placeholder="choose an agent">
          <el-option v-for="(agent, id) in board.agents" :key="id" :value="id"
                     :label="`${id} · ${agent.kind}`" :disabled="id === board.writer" />
        </el-select>
      </el-form-item>
      <el-form-item label="subject">
        <el-input v-model="directSubject" placeholder="what decision or instruction is this?" />
      </el-form-item>
      <el-form-item label="message">
        <el-input v-model="directBody" type="textarea" :rows="5"
                  placeholder="markdown is recorded and requires a receipt" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="directDialog = false">cancel</el-button>
      <el-button type="primary" :loading="directBusy" :disabled="!directPeer || !directBody.trim()"
                 @click="sendDirect">send and require receipt</el-button>
    </template>
    <el-alert v-if="directError" type="error" :closable="false" show-icon
              title="The tool refused this message">
      <pre class="aim-mono">{{ directError }}</pre>
    </el-alert>
  </el-dialog>
</template>

<style scoped>
/* The header is a column now, because it has two things to say: what the channel
   is (the title line, the gate, what it holds) and what it is for (the topic,
   above the stream). It was one flex row, which is why the topic had nowhere to
   sit except on the same line as the id, and the pane's own CSS has always said
   why that matters -- "a reader who has just arrived" reads the head before the
   first message, so a purpose printed below the log is not what the channel is
   for. `flex-direction` is the only thing overridden; the sticky position, the
   z-index and the background stay in `style.css`, where the class's layout is. */
.aim-reader-head { flex-direction: column; align-items: stretch; }
.aim-reader-headline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.aim-reader-topic { font-size: 12.5px; line-height: 1.6; margin-top: 4px; }
.aim-reader-participants { font-size: 11px; margin-top: 2px; }

/* A channel's topic in the list, which is long on purpose: `hello`'s is a whole
   question. Two lines are enough to tell a transport check from the development
   channel, and the row stays a row. */
.aim-thread-topic { font-size: 11px; margin-top: 3px; line-height: 1.45;
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                    overflow: hidden; }
.aim-probe, .aim-held { font-size: 10.5px; }
</style>
