<script setup>
import { computed, inject, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { isPromise, useBoard } from '../stores/board'
/**
 * The one predicate for "this message is waiting on the reader", taken from the
 * pane that owns the `needs me` filter rather than written again here.
 *
 * T-0162 is what a second derivation costs: this page asked whether the *row*
 * carried a receipt chip, and the answer was yes for demands the reader had sent
 * and demands addressed to another agent. A count and the list it lands on have
 * to be one question asked once.
 */
import { messageWaiting } from './ChatPane.vue'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import PhaseApprovalCard from '../components/PhaseApprovalCard.vue'
import PromiseTag from '../components/PromiseTag.vue'
import TaskLink from '../components/TaskLink.vue'

const ctx = inject('ctx')
const drawer = ctx.service('taskDrawer')
const api = ctx.service('api')
const board = useBoard()
/**
 * Busy and refusal are keyed by the action, not held for the page.
 *
 * One `actionError` for a whole page is the defect T-0165 names: a receipt
 * refused on a message row was drawn by `PhaseApprovalCard.vue:62` inside every
 * phase-request card the reader never touched, because `:error` is a prop of
 * that card and this pane passed it one page-wide string. Measured on a fixture
 * of two requests and one message row (`web/tests/card-t0165-row-feedback.spec.js`):
 * a `confirm` refusal came back on both request cards and nowhere on the row that
 * asked for it, and an `advance` refusal for channel `alpha` came back on the
 * `beta` card too.
 *
 * So the state is a map from the command's own identity to what it produced.
 * The identity is not invented here: it is the string each control already
 * compares against for its `loading` -- `confirm:<msg_id>` on a message row,
 * `advance:<channel>:<ts>` and `reject:<channel>:<ts>` in
 * `PhaseApprovalCard.vue:50,55` -- which is why the busy half of the card's
 * acceptance already measured green and only the refusal half was red. The
 * phase cards cannot borrow the row's identity or each other's: `ts` is the
 * request's own timestamp and `channel` its own channel, and two requests on one
 * channel cannot share a `ts`.
 *
 * The map is bounded rather than grown: a board left open for a day of failed
 * clicks would otherwise hold one string per attempt forever. Clearing entries
 * does not clear a refusal still on screen, because a card draws one only for
 * its own key; that is what keeps the bound from lying about the record.
 */
const ERRORS_KEPT = 20
const actionBusy = ref('')
const actionErrors = ref({})
const errorFor = (name) => actionErrors.value[name] || ''

const noteError = (name, message) => {
  const next = { ...actionErrors.value, [name]: message }
  const keys = Object.keys(next)
  for (const stale of keys.slice(0, Math.max(0, keys.length - ERRORS_KEPT))) delete next[stale]
  actionErrors.value = next
}

/**
 * Every count on this page is work, and work is on the record.
 *
 * `board.tasks` is two disjoint universes merged server-side -- the plan's static
 * seeds and the items a person recorded -- and a count over that merge answers a
 * question nobody asked. Measured live before this: "4 overdue", none of them on
 * the record; "6 blocked", none of them; "1 in review", none. The leader read
 * that page and said they could not tell what to look at, which is what a summary
 * says when it counts promises as work. A promise is not work: there is no item
 * to move, so there is nothing for the reader to fail to do.
 *
 * So the signals read `recorded`, the promises are counted separately and in
 * their own words (see the plan card below), and the drift between the two is
 * still on the page -- as the disagreement it is, not as four overdue rows.
 */
const overdue = computed(() => board.recordedOverdue)
const blocked = computed(() => board.recordedByStatus.blocked || [])
const review = computed(() => board.recordedByStatus.review || [])

/**
 * Receipts the *reader* still owes, read row by row off the recipient.
 *
 * What this replaces: `board.unacked.length`, a server list that is a property of
 * every inbox under `outbox/` rather than of the reader. Measured live as
 * `human`: 15, of which 11 were `codex -> claude-session1` -- mail the reader
 * never received and can never answer. The same list also counted demands the
 * reader had sent, so the tile said "15 receipts owed" beside a sender's own
 * outgoing chips, and a row that reads `acked` and `receipt demanded` side by
 * side is the defect T-0162 names.
 *
 * A mail row on the wire carries `from`, `to`, `ack_required` and `state`; the
 * predicate is Chat's `messageWaiting`, imported rather than restated, so the
 * number here and the `needs me` filter there are one question asked once. The
 * room half of T-0162 -- unread state per viewer -- is Chat's, and this tile
 * does not claim it: rooms have no receipt to owe.
 *
 * `board.ackOwed` is where this belongs, beside `unacked`; it is here because
 * `web/src/stores/board.js` is another agent's file this round. If it moves, the
 * tile reads the getter and the list under it shrinks to the rows the reader
 * owes.
 * The cap is drawing, not counting: a thousand-row page is not a summary, and
 * the count stays the record's own number.
 */
const receiptsOwed = computed(() => board.conversationRows
  .filter((row) => row.shape === 'direct' && messageWaiting(row, board.viewer)))
const RECEIPTS_DRAWN = 40

/**
 * The list the receipts tile lands on: the Chat threads holding a message the
 * reader owes, newest first.
 *
 * Both keys are Chat's own (`needsMe` is its checkbox, `thread` is the key its
 * watcher selects), because a query the destination does not read is a link that
 * lands on the whole board and reports a filter. For a direct thread "waiting on
 * the viewer" and "the reader owes a receipt" are the same fact, so
 * `needsMe=1&shape=direct` lands on exactly these threads; the one-thread case
 * names the thread as well, so it opens on the conversation rather than the list.
 * The tile counts messages and the list shows conversations -- the card between
 * them is what names the messages.
 */
const receiptThreads = computed(() => {
  const byThread = new Map()
  for (const row of board.conversationRows) {
    if (row.shape !== 'direct') continue
    const key = threadKey(row)
    const entry = byThread.get(key) || { key, owed: [] }
    if (messageWaiting(row, board.viewer)) entry.owed.push(row)
    byThread.set(key, entry)
  }
  return [...byThread.values()]
    .filter((entry) => entry.owed.length)
    .sort((a, b) => (a.owed.at(-1).ts < b.owed.at(-1).ts ? 1 : -1))
})

/**
 * A signal is a way in, and a signal with nothing behind it is not.
 *
 * The count and the destination are one thing: `3 overdue` has to land on the
 * three, or the reader learns that the numbers here are decorative. So the
 * destination is built by the same function that counts, and a card at zero is
 * drawn as a plain tile with no link at all -- a card that says "0 needs action"
 * and then navigates somewhere is the summary that lies.
 *
 * A non-zero signal carries the sentence a reader would otherwise have to infer
 * from the page: that the number is on the record. It is worth the pixels,
 * because the promise count looks identical and means something else.
 *
 * `target` is the drawer-or-list decision: an item that wants attention because
 * it *is* a work item opens that work item; a category opens the list filtered
 * to itself.
 */
const signals = computed(() => [
  { label: 'Overdue', value: overdue.value.length, type: 'danger',
    detail: 'on the record', to: { path: '/items', query: { onlyLate: '1' } } },
  { label: 'Blocked', value: blocked.value.length, type: 'danger',
    detail: 'on the record', to: { path: '/items', query: { status: 'blocked' } } },
  { label: 'Review', value: review.value.length, type: 'warning',
    detail: 'on the record', to: { path: '/items', query: { status: 'review' } } },
  { label: 'Phase requests', value: board.phaseRequests.length, type: 'danger',
    detail: 'on the record', to: { path: '/attention', hash: '#leader-decisions' } },
  { label: 'Receipts owed', value: receiptsOwed.value.length, type: 'warning',
    detail: 'addressed to you', to: {
      path: '/chat',
      query: receiptThreads.value.length === 1
        ? { needsMe: '1', thread: receiptThreads.value[0].key }
        : { needsMe: '1', shape: 'direct' },
    } },
  { label: 'Plan disagreements', value: board.drift.length, type: 'warning',
    detail: 'plan vs store', to: { path: '/attention', hash: '#drift' } },
])

const attentionTasks = computed(() => board.recorded
  .filter((task) => {
    if (board.terminal.includes(task.status)) return false
    return task.status === 'blocked'
      || task.status === 'review'
      || isOverdue(task.due, task.status, board.terminal)
      || (task.status === 'doing' && task.priority === 'high')
  })
  .sort((a, b) => {
    const rank = (task) => (task.status === 'blocked' ? 0 : task.status === 'review' ? 1 : 2)
    return rank(a) - rank(b) || (a.due || '9999').localeCompare(b.due || '9999')
  })
  .slice(0, 8))

/** A receipt announces itself in its subject: `RECEIPT for <msg_id>`. */
const receiptRe = /^RECEIPT for\s+/
/**
 * The message a receipt names, which is the whole point of the receipt.
 *
 * Measured 2026-09-22 over the live payload: 53 of 53 receipts yield an id from
 * the subject, and all 53 ids are present as `msg_id` in `conversation.mail`, so
 * the subject is the id and not a paraphrase of one.
 */
const receiptedId = (row) => (row.subject || '').replace(receiptRe, '').trim()

/**
 * Every receipt the payload holds, grouped by the conversation it arrived in.
 *
 * The number a reader is shown has to be a property of the record, not of the
 * five rows this card draws. The expression this replaces counted
 * `conversationRows.slice(-5).filter(isReceipt)`, so the number was `min(5, n)`
 * of the window. Measured against the bundle on 8777 (its
 * `dist/assets/OverviewPane-*.js` holds `slice(-5)` and `receipts arrived`) with
 * a fixture of seven receipts spread over three minutes and fifteen ordinary
 * rows after them: the card said nothing about receipts at all, five raw rows
 * only. With the same fifteen rows removed the card said "5 receipts arrived",
 * and with one ordinary row after the burst it did not collapse and drew a raw
 * `RECEIPT for ...` row. On the live payload -- 197 flattened rows, 53 receipts
 * -- the five newest rows hold 0 receipts, so no receipt row is drawn. Seven
 * arrived and the page said nothing, then five, then one: one record, three
 * answers, because the number was a property of the window.
 *
 * Grouped by conversation (`threadKey`, the key the row's own link uses) because
 * that is the question a row can answer -- "this thread received N receipts" --
 * and because the group's newest receipt is then the row the count can sit on.
 * This derivation belongs in the store beside `conversationRows`, one rule asked
 * once, and it is here only because `board.receiptGroups` does not exist yet;
 * measured, `grep -r RECEIPT web/src` names this file and nothing else, so there
 * is no second consumer to drift from today.
 */
const receiptGroups = computed(() => {
  const byKey = new Map()
  for (const row of board.conversationRows) {
    if (!receiptRe.test(row.subject || '')) continue
    const key = threadKey(row)
    let group = byKey.get(key)
    if (!group) {
      group = { key, shape: row.shape, scope: row.scope, size: 0, latest: row, receipts: [] }
      byKey.set(key, group)
    }
    group.size += 1
    group.receipts.push({ id: receiptedId(row), from: row.from, ts: row.ts, msg_id: row.msg_id || '' })
    // `>`, not `>=`: on a tie the earlier row stays, and `conversationRows` is
    // ascending by `ts`, so the earliest row of a tie is the one already held.
    if (String(row.ts ?? '') > String(group.latest.ts ?? '')) group.latest = row
  }
  // Newest first, by the same rule that picked `latest`: a stable descending
  // sort, so rows on an equal `ts` keep payload order and the head of this list
  // is the row `latest` points at. A plain `reverse()` was not that rule -- it
  // put the *last* row of a tie first, so a group whose receipts share a `ts`
  // opened its panel on a line that was not the row's own newest (measured: two
  // receipts at one `ts` -> `latest` the first, panel headed by the second).
  // `??`/`String` because the store's own comparator (`a.ts < b.ts`, board.js:348)
  // orders a numeric `ts` against a string instead of throwing; comparing two
  // strings here keeps this sort and `latest` the same rule for every type the
  // payload can carry, rather than for the string one it always carries today.
  for (const group of byKey.values()) {
    group.receipts.sort((a, b) => (String(a.ts ?? '') < String(b.ts ?? '') ? 1
      : String(a.ts ?? '') > String(b.ts ?? '') ? -1 : 0))
  }
  return byKey
})

/**
 * The five newest rows, with a conversation's receipts collapsed into one.
 *
 * Three things changed:
 *
 *  * the count is `group.size`, taken over the whole payload, so it cannot move
 *    when the window moves;
 *  * the row that survives is the group's **newest** receipt. The old row was
 *    the newest receipt *inside the window* -- `slice(-5).reverse()` puts the
 *    newest first, so `receipts[0]` was that row and the collapse kept it, which
 *    is why the card was right about the date in a 394ms burst. It stopped being
 *    right the moment a newer receipt fell out of the five: measured, a group
 *    running 00:00…00:03 loses its row entirely once five ordinary rows follow
 *    it. The date was a property of the window, like the count.
 *  * the row carries the list it counts, so "7 receipts arrived" is a way in
 *    rather than a number with nothing behind it.
 *
 * The collapse is still partial in the way it was measured -- a conversation
 * that received more than one receipt is drawn **once**, by its newest receipt,
 * with the count of all of them, and no member of the group is drawn beside it.
 * What did not change is the identity the old expression rested on: `filter`
 * over the window returns a new array of the *same* row objects, so
 * `row === group.latest` matches the one row it should. That identity was
 * measured (`rows 5, receipts 5, identity match: true, result rows: 1`), and the
 * result measured here is the shape this keeps.
 *
 * The identity is load-bearing and it rests on `board.conversationRows` being
 * one cached getter: both `receiptGroups` and this computed read it, and Pinia
 * answers the second read with the same objects. If that ever becomes a
 * function that builds fresh rows per call -- `board.conversationRows()` -- then
 * no receipt row matches its group's `latest`, every one of them is skipped, and
 * the card silently draws nothing for that conversation. The collapse's own
 * failure mode is that quiet: `web/tests/receipts.spec.js` asserts the counted
 * row exists (`TAIL_BURST` -> one row), which is what would catch it.
 *
 * The probe caught the first draft of this drawing the older receipts of a
 * counted group as raw `RECEIPT for ...` rows underneath the count -- a group
 * of seven showed one collapsed row plus four raw subjects in the same window.
 * A group's count stands for its members or it does not.
 *
 * A conversation whose newest receipt is older than the window draws no row --
 * there is no row to draw it on. That is the same silence the old expression
 * produced in that case (measured: fifteen ordinary rows after a burst of seven
 * -> no receipt row), and it is why the count belongs to a row and not to the
 * card: the card is a window, the number is the record.
 */
const recentConversations = computed(() => {
  const groups = receiptGroups.value
  const rows = []
  for (const row of board.conversationRows.slice(-5).reverse()) {
    // Only a receipt row can be absorbed into its group's count. A group is
    // keyed by conversation, and an ordinary message in that same conversation
    // is not one of the members the count stands for: the first draft of this
    // dropped them (`group` matches on the pair, not on the receipt), which the
    // probe caught immediately -- three ordinary rows in a receipted
    // conversation vanished from a card that drew one row instead of four.
    if (!receiptRe.test(row.subject || '')) {
      rows.push(row)
      continue
    }
    const group = groups.get(threadKey(row))
    // `size <= 1` keeps one receipt drawn as the row it is, subject and all.
    if (!group || group.size <= 1) {
      rows.push(row)
      continue
    }
    if (row !== group.latest) continue
    rows.push({ ...row, receiptCount: group.size, receipts: group.receipts,
                subject: `${group.size} receipts arrived` })
  }
  return rows
})
const upcomingMilestones = computed(() => Object.values(board.milestones)
  .map((milestone) => {
    // The meter measures recorded work, like every other number here: a milestone
    // whose items are all promises is a milestone at zero, and drawing 87% of a
    // plan file as progress is the same lie as "15 overdue".
    const tasks = board.recorded.filter((task) => task.milestone === milestone.id)
    // A dismissed item is in neither figure, which is the server's own rule for
    // this exact question -- `aimboard/api.py:461`, `scored = total -
    // counts.get("dropped", 0)`, under the comment that counting it done
    // "flatters the board" while counting it undone "keeps a card that was
    // deliberately closed open forever". `terminal` is `["done","dropped"]`
    // (`aimboard/const.py:11`), so `terminal.includes` alone read a dismissal as
    // a completion. Subscripting the one member out rather than retyping
    // `["done"]` is `api.py:453`'s reasoning applied here: the authority stays
    // with the constant, and the expression says which of its members it means.
    //
    // Measured 2026-09-22 on this tree, `/api/state` folded at `date(2026,9,22)`:
    // 90 recorded items across 10 milestones, and exactly one of the 90 is
    // `dropped` -- T-0174, which names no milestone at all. So all ten milestones
    // score the same either way today and the defect this rule closes is latent,
    // not live. What it closes: a milestone whose only recorded item was dismissed
    // scored `done/total` `1/1`, `pct 100`, and the `pct < 100` filter below then
    // removed it from "Next milestones" entirely -- a dismissed card drawn as a
    // milestone reaching completion. Rounded towards done is the one direction this
    // page must never round in, which is why the denominator moves with the
    // numerator here: an all-dismissed milestone scores 0 of 0, fails the filter's
    // `milestone.total` test, and is drawn as nothing rather than as progress.
    const finished = board.terminal.filter((status) => status !== 'dropped')
    const scored = tasks.filter((task) => task.status !== 'dropped')
    const done = scored.filter((task) => finished.includes(task.status)).length
    return { ...milestone, done, total: scored.length,
             pct: scored.length ? Math.round(100 * done / scored.length) : 0 }
  })
  .filter((milestone) => milestone.total && milestone.pct < 100)
  .sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'))
  .slice(0, 3))

const clear = computed(() =>
  signals.value.every((signal) => signal.value === 0)
  && !receiptsOwed.value.length
  && !attentionTasks.value.length && !board.promiseDecisions.length)
const preview = (message) => message.subject || message.body || '(nothing yet)'
const taskRecorded = (task) => !isPromise(task)
const threadKey = (message) => {
  if (message.shape === 'channel') return `ch:${message.channel}`
  if (message.shape === 'room') return `room:${message.channel}/${message.room}`
  return `dm:${message.scope}`
}

function openTask(task) {
  drawer.open(task.id, { tasks: board.tasks })
}

/**
 * The drawer's move vocabulary, copied deliberately and kept small.
 *
 * These are the words on the buttons in `TaskDecisionDrawer`'s action panel --
 * the panel a click on this row opens. They are here rather than imported
 * because the drawer names them in its template and nothing else, and a shared
 * constant for four strings would be a module whose only job is to be imported.
 * What matters is that they *are* the same words: a row that promises an act the
 * panel does not contain is a row that lies, and this page has already done that.
 */
const MOVE_LABEL = {
  backlog: 'make ready',
  ready: 'start doing',
  blocked: 'start doing',
  doing: 'send to review',
}

/**
 * What the row's button promises, in the vocabulary the drawer actually offers.
 *
 * This is the "Work needing you now" list, and T-0180 made it draw recorded items
 * only (`board.recorded`), so every row here is something the store can already
 * move: the drawer's panel for each of them is the status moves above, plus the
 * review decisions at `review`. The previous version named the *category* instead
 * ("unblock or decide") and was measured wrong on this page -- a recorded item in
 * `blocked` got a row promising an unblock control that the panel does not have,
 * because `blocked -> done` is not a move this fabric offers.
 *
 * When the T-0176 work lands its shared predicate, this becomes one call to it.
 * Until then the honest thing is to promise only what the next click delivers.
 */
function taskActionLabel(task) {
  if (taskRecorded(task) && task.status === 'review') return 'accept or return'
  return MOVE_LABEL[task.status] || 'inspect'
}

async function runAction(name, argv) {
  actionBusy.value = name
  noteError(name, '')
  const result = await api.command(argv)
  actionBusy.value = ''
  if (result.rc !== 0) {
    // Keyed on the way out as well as on the way in. The name is computed from
    // the row or the card the reader clicked and not from the command's argv, so
    // a control that derives the identity differently from this call would record
    // its refusal under a key nothing draws -- the same silence as the page-wide
    // string, one indirection later.
    noteError(name, result.stderr || result.stdout || `aim exited ${result.rc}`)
    return
  }
  await board.load()
}

/** The identity a message row's own controls use, and the one its refusal is filed under. */
const confirmKey = (msgId) => `confirm:${msgId}`
const confirmArgv = (msgId) => ['confirm', '--msg-id', msgId, '--note', 'confirmed from attention page']

/**
 * Which rows offer the receipt, and therefore which rows may draw its refusal.
 *
 * Both cards that draw a demand draw the button only under a condition, and a
 * row that offers no control must not annotate a failure it did not initiate --
 * which is the clause the card states as "a failure in one action does not
 * disable or annotate unrelated rows". The predicate is written once so the
 * button and the alert cannot disagree about which row is the one that asked.
 * `Latest conversation` has no viewer condition because it is a transcript of
 * what arrived, not a list of what the reader owes.
 */
const canConfirm = (row) => row.shape === 'direct' && Boolean(row.ack_required) && !row.acked_at

/**
 * The chain card draws the receipt only for the seat the demand is addressed to
 * (`unacked` is the whole fabric's list, not the viewer's), so only those rows
 * may draw what that command returned.
 */
const isAddressee = (item) => item.to === board.viewer

async function approvePhase(request) {
  await runAction(`advance:${request.channel}:${request.ts}`, [
    'advance', '--channel', request.channel, '--to', request.targetPhase,
    '--note', 'approved from the attention page',
  ])
}

async function rejectPhase(request, reason) {
  await runAction(`reject:${request.channel}:${request.ts}`, [
    'say', '--channel', request.channel, '--kind', 'note',
    '--subject', `declined: ${request.fromPhase} -> ${request.targetPhase}`,
    '--body', `The leader declined this phase request. Reason: ${reason}`,
  ])
}
</script>

<template>
  <section class="aim-attention">
    <header class="aim-attention-hero">
      <div>
        <p>Attention</p>
        <h3>{{ clear ? 'Nothing needs you right now' : 'Start here' }}</h3>
        <span>
          {{ board.phaseRequests.length }} phase request(s) · {{ overdue.length }} overdue ·
          {{ blocked.length }} blocked · {{ review.length }} review ·
          {{ receiptsOwed.length }} receipts owed
        </span>
        <span class="aim-dim" style="display:block">
          every count here is work on the record, and a receipt count is mail addressed to you —
          the plan's promises are counted separately, below
        </span>
      </div>
      <div>
        <RouterLink to="/items">All work items</RouterLink>
        <RouterLink to="/chat">All conversations</RouterLink>
      </div>
    </header>

    <div class="aim-attention-signals">
      <component :is="signal.value ? RouterLink : 'div'" v-for="signal in signals" :key="signal.label"
                 :to="signal.value ? signal.to : undefined"
                 class="aim-signal" :class="{ 'aim-signal-clear': !signal.value }"
                 :aria-disabled="signal.value ? undefined : 'true'"
                 :title="signal.value
                   ? `${signal.value} ${signal.label.toLowerCase()}, ${signal.detail}`
                   : `${signal.label}: nothing on the record`">
        <span>{{ signal.value }}</span>
        <strong>{{ signal.label }}</strong>
        <!-- The tag names what the number counts, which is the one thing the page
             cannot afford to leave to inference: a promise and a work item look
             identical in this row, and only one of them is something to do. -->
        <el-tag :type="signal.type" size="small" effect="plain">
          {{ signal.value ? signal.detail : 'clear' }}
        </el-tag>
      </component>
    </div>

    <!-- What needs a human comes first. The order of this page is the answer to
         概念太多了: the cards that want a decision are above the cards that only
         report, and the diagnostics are last, where a reader who wants them can
         go looking. -->
    <el-card v-if="board.phaseRequests.length" id="leader-decisions" shadow="never" class="aim-phase-card">
      <template #header><span>Leader decisions</span><RouterLink to="/barrier">audit barrier</RouterLink></template>
      <PhaseApprovalCard v-for="request in board.phaseRequests"
                         :key="`${request.channel}:${request.ts}:${request.from}`"
                         :request="request" :busy="actionBusy"
                         :error="errorFor(`advance:${request.channel}:${request.ts}`)
                           || errorFor(`reject:${request.channel}:${request.ts}`)"
                         @approve="approvePhase" @reject="rejectPhase" />
    </el-card>

    <!-- What the reader still owes, named by the message that is waiting.
         This card is the receipts tile opened out: same predicate, same rows, so
         the number at the top and this list cannot disagree. Every row is
         addressed `to` the viewer and unacked, and the button beside it is the
         one command that answers it — the same `confirm` the Chat reader runs.

         The row carries its own refusal, and the refusal is drawn *inside* the
         `<article>`: `role="button"` makes that element the innermost one holding
         the text, and a wrapper placed outside it would be attributed to the page
         rather than to the row that asked for the action -- which is the question
         the card asks. It is the last child so the grid's auto-placement keeps
         every earlier cell where `.aim-attention-row` (style.css:173) puts it,
         and it spans the row with an inline `grid-column`, the shell stylesheet
         being another task's file. The `<pre>` is where the mono class and the
         error colour live: on the alert they would make the alert itself the
         innermost element holding the text, and the surface the card reads would
         then be Element's wrapper rather than this pane's row. -->
    <el-card v-if="receiptsOwed.length" id="receipts-owed" shadow="never" class="aim-receipts-card">
      <template #header>
        <span>{{ receiptsOwed.length }} message(s) addressed to you, unacked</span>
        <RouterLink :to="signals.find((s) => s.label === 'Receipts owed').to">open in chat</RouterLink>
      </template>
      <article v-for="row in receiptsOwed.slice(0, RECEIPTS_DRAWN)"
               :key="row.msg_id || `${row.scope}:${row.ts}`"
               class="aim-attention-row aim-clickable"
               role="button" tabindex="0"
               :aria-label="`Open the conversation ${row.scope}, which owes you a receipt`"
               @click="$router.push({ path: '/chat', query: { thread: threadKey(row), msg: row.msg_id } })"
               @keydown.enter.prevent="$router.push({ path: '/chat', query: { thread: threadKey(row), msg: row.msg_id } })">
        <span class="aim-mono">{{ (row.ts || '').slice(0, 10) }}</span>
        <strong>{{ row.subject || '(no subject)' }}</strong>
        <span>{{ row.from }} → {{ row.to }}</span>
        <el-tag size="small" type="warning" effect="plain">unacked</el-tag>
        <el-button size="small" text
                   :loading="actionBusy === confirmKey(row.msg_id)"
                   @click.stop="runAction(confirmKey(row.msg_id), confirmArgv(row.msg_id))">
          confirm receipt
        </el-button>
        <el-alert v-if="errorFor(confirmKey(row.msg_id))" type="error" :closable="false" show-icon
                  style="grid-column:1 / -1" title="The tool refused this action">
          <pre class="aim-mono">{{ errorFor(confirmKey(row.msg_id)) }}</pre>
        </el-alert>
      </article>
      <p v-if="receiptsOwed.length > RECEIPTS_DRAWN" class="aim-dim" style="font-size:12px;margin-bottom:0">
        {{ receiptsOwed.length - RECEIPTS_DRAWN }} more than this card draws. The count above is the record's.
      </p>
    </el-card>

    <!-- The promises, counted out loud and in their own words.
         They are on this page because the reader is entitled to see what the plan
         claims -- but they are not work, so they are not in a work signal, and
         the sentence says how many of them are actually addressed to the person
         reading. A promise with `owner: human` and status `ready` is a decision
         the plan has parked on the leader; before this it was drawn as an overdue
         work item the leader had failed to move, which is the row they pointed
         at with "human 没有可以处理的方法". -->
    <el-card shadow="never" class="aim-promise-card">
      <template #header>
        <span><PromiseTag /> {{ board.promiseSummary.text }}</span>
        <RouterLink to="/plan">the plan itself</RouterLink>
      </template>
      <p class="aim-dim" style="font-size:12px;margin-top:0">
        A promise has no work item behind it, so this page does not count it as overdue,
        blocked or in review. Where the plan and the store disagree, the store wins — the
        disagreement itself is under “Plan and store disagree”, at the bottom of this page.
      </p>
      <article v-for="task in board.promiseDecisions" :key="task.id"
               class="aim-attention-row aim-clickable"
               role="button" tabindex="0" :aria-label="`Open the plan promise ${task.id}: ${task.title}`"
               @click="openTask(task)"
               @keydown.enter.prevent="openTask(task)"
               @keydown.space.prevent="openTask(task)">
        <span class="aim-mono">{{ task.id }}</span>
        <strong>{{ task.title }}</strong>
        <PromiseTag title="A plan promise, not a recorded item: the plan says its owner is you." />
        <el-tag size="small" type="warning" effect="dark">decision for you</el-tag>
        <el-button size="small" text @click.stop="openTask(task)">open it</el-button>
      </article>
    </el-card>

    <!-- What the record says about one message, one fact at a time.
         `pending receipt` here is the *condition*, true of a demand nobody has
         answered, and the chain names the rule while the rows under it are the
         ones the viewer owes — so the page never draws a message that is `acked`
         beside one that still says `receipt demanded`. The button is drawn from
         the same predicate the tile counts, not from the row's own chip. -->
    <el-card v-if="board.unacked.length" id="ack-chain" shadow="never" class="aim-ack-card">
      <template #header>
        <span>{{ board.unacked.length }} message(s) in the fabric demand an acknowledgement</span>
        <RouterLink to="/help">what a receipt is</RouterLink>
      </template>
      <p class="aim-dim" style="font-size:12px;margin-top:0">
        A demand is outstanding until somebody answers it. Whether that somebody is you is the
        question the receipts tile answers, by recipient; this card is the whole chain, so a
        message you sent and a message awaiting you are not read as one list.
      </p>
      <article v-for="item in board.unacked.slice(0, 8)" :key="item.msg_id" class="aim-attention-row">
        <span class="aim-mono">pending receipt</span>
        <strong class="aim-mono">{{ item.msg_id }}</strong>
        <span>{{ item.from }} → {{ item.to }}</span>
        <el-tag v-if="item.to === board.viewer" size="small" type="warning" effect="dark">addressed to you</el-tag>
        <el-tag v-else size="small" effect="plain">another seat</el-tag>
        <el-button v-if="isAddressee(item)" size="small" text
                   :loading="actionBusy === confirmKey(item.msg_id)"
                   @click.stop="runAction(confirmKey(item.msg_id), confirmArgv(item.msg_id))">
          confirm receipt
        </el-button>
        <!-- Drawn under the same condition as the button: a row showing "another
             seat" offers no receipt, so a refusal that arrived while the reader
             was on this page must not be read as that row's. -->
        <el-alert v-if="isAddressee(item) && errorFor(confirmKey(item.msg_id))"
                  type="error" :closable="false" show-icon
                  style="grid-column:1 / -1" title="The tool refused this action">
          <pre class="aim-mono">{{ errorFor(confirmKey(item.msg_id)) }}</pre>
        </el-alert>
      </article>
    </el-card>

    <el-alert v-if="board.withheld" type="info" :closable="false" show-icon>
      <template #title>
        {{ board.withheld }} peer record(s) are withheld by the barrier. Audit the gate in its own page.
      </template>
      <template #default><RouterLink to="/barrier">Open audit</RouterLink></template>
    </el-alert>

    <div class="aim-attention-columns">
      <el-card shadow="never">
        <template #header><span>Work needing you now</span><RouterLink to="/items">see all</RouterLink></template>
        <el-empty v-if="!attentionTasks.length" description="no recorded item is overdue, blocked, in review or high-priority doing" :image-size="70" />
        <article v-for="task in attentionTasks" :key="task.id" class="aim-attention-row aim-clickable"
                 role="button" tabindex="0" :aria-label="`Open task ${task.id}: ${task.title}`"
                 @click="openTask(task)"
                 @keydown.enter.prevent="openTask(task)"
                 @keydown.space.prevent="openTask(task)">
          <span class="aim-mono">{{ task.id }}</span>
          <strong>{{ task.title }}</strong>
          <el-tag size="small" :type="STATUS_TYPE[task.status] || 'info'" effect="dark">{{ task.status }}</el-tag>
          <el-tag size="small" :type="PRIORITY_TYPE[task.priority] || 'info'" effect="plain">{{ task.priority }}</el-tag>
          <span>{{ task.owner || 'unassigned' }}</span>
          <span :class="{ 'aim-late': isOverdue(task.due, task.status, board.terminal) }">{{ task.due || 'no date' }}</span>
          <el-button size="small" text @click.stop="openTask(task)">{{ taskActionLabel(task) }}</el-button>
        </article>
      </el-card>

      <el-card shadow="never">
        <template #header><span>Latest conversation</span><RouterLink to="/chat">read and reply</RouterLink></template>
        <el-empty v-if="!recentConversations.length" description="no conversation on the record" :image-size="70" />
        <article v-for="message in recentConversations"
                 :key="`${message.shape}:${message.msg_id || message.hash || message.ts}`"
                 class="aim-attention-row">
          <strong>{{ message.from }}</strong>
          <span>{{ message.scope }}</span>
          <!-- A row that counts N receipts is a way into the N.
               Before this, "7 receipts arrived" was a number with nothing behind
               it: the row's link was the surviving receipt's own -- `threadKey`
               of the newest receipt of the window, so it landed on the busy
               conversation the receipts arrived in, not on the messages they
               receipted. The rows in the panel are the `receipts` list the count
               was taken from -- the number and the list are one read of the
               record -- and each id is a `msg_id` in that payload (measured: 53
               of 53 live receipt ids are present as `msg_id`), so what the panel
               names is an address the record can answer. -->
          <!-- The width is capped against the viewport rather than fixed at 420, and
               the panel is allowed to flip to the left when there is no room on
               the right: measured on the built bundle at a 390px viewport, a
               fixed 420px panel at `placement="right"` rendered at x 367..726 --
               336px of it off a 390px screen -- and a capped 384px panel still
               rendered at x 367..726, i.e. the cap alone does not move it. The
               `.el-popper` stays in the DOM when closed (`persistent` is
               Element Plus's default for `el-popover`), so flipping beats
               growing: `top`/`bottom` would leave the panel 384px tall inside a
               900px window. `width` takes a CSS length and `style.css` is
               another task's file right now. -->
          <el-popover v-if="message.receiptCount" placement="right" :width="'min(420px, 92vw)'"
                      :fallback-placements="['left', 'bottom']" trigger="click">
            <template #reference>
              <!-- A `button`, not a link: opening this reads the group, it does not
                   navigate. `style.css` is another task's file right now, so the
                   button chrome is neutralised here rather than by adding a rule
                   next to `.aim-task-link`, which is the same reset. -->
              <button type="button" class="aim-row-link"
                      style="background:none;border:0;padding:0;font:inherit;text-align:left;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ preview(message).slice(0, 72) }} · show them
              </button>
            </template>
            <p class="aim-dim" style="font-size:12px;margin:0 0 8px">
              {{ message.receiptCount }} receipts arrived in {{ message.scope }},
              newest first. Each line names the message that was receipted.
            </p>
            <!-- The one scroller this page owns, and it is capped on purpose.
                 `scrolledContainers` snapshots every element the reader has
                 scrolled, so a group of 53 receipts cannot push the landing page
                 itself into being a restore target, and a forced update puts the
                 reader back on the line of the panel they were reading. -->
            <div style="max-height:240px;overflow-y:auto">
              <div v-for="receipt in message.receipts" :key="receipt.msg_id || `${receipt.id}:${receipt.ts}`"
                   style="display:flex;gap:10px;align-items:baseline;border-top:1px solid var(--aim-line-soft);padding:5px 0">
                <span class="aim-mono">{{ (receipt.ts || '').slice(0, 16).replace('T', ' ') }}</span>
                <strong>{{ receipt.from }}</strong>
                <span class="aim-mono">{{ receipt.id }}</span>
              </div>
            </div>
          </el-popover>
          <RouterLink v-else :to="{ path: '/chat', query: { thread: threadKey(message) } }" class="aim-row-link">
            {{ preview(message).slice(0, 72) }}
          </RouterLink>
          <el-tag size="small" effect="plain">{{ message.shape }}</el-tag>
          <span>{{ (message.ts || '').slice(0, 16).replace('T', ' ') }}</span>
          <el-button v-if="canConfirm(message)"
                     size="small" :loading="actionBusy === confirmKey(message.msg_id)"
                     @click="runAction(confirmKey(message.msg_id), confirmArgv(message.msg_id))">
            confirm receipt
          </el-button>
          <!-- The same key the row above the fold files under, because it is the
               same command on the same message: one action, one refusal, wherever
               the reader took it from. The condition is the button's, so a logged
               `acked` row -- which offers nothing -- never explains a failure. -->
          <el-alert v-if="canConfirm(message) && errorFor(confirmKey(message.msg_id))"
                    type="error" :closable="false" show-icon
                    style="grid-column:1 / -1" title="The tool refused this action">
            <pre class="aim-mono">{{ errorFor(confirmKey(message.msg_id)) }}</pre>
          </el-alert>
        </article>
      </el-card>
    </div>

    <!-- Reports, after everything a reader can act on and in the order a reader
         wants them: the work that is still to come, then the disagreement that
         explains why this page's numbers and the plan's differ. The drift card
         used to sit above the only card the leader could act on and push it below
         the fold; the fact it reports has not changed (one plan/record
         disagreement renders as one row per field), but its place in the reading
         order has. -->
    <el-card shadow="never" class="aim-attention-milestones">
      <template #header><span>Next milestones</span><RouterLink to="/plan">full plan</RouterLink></template>
      <el-empty v-if="!upcomingMilestones.length" description="no unfinished milestone with recorded items" :image-size="70" />
      <article v-for="milestone in upcomingMilestones" :key="milestone.id" class="aim-attention-row">
        <span class="aim-mono">{{ milestone.id }}</span>
        <strong>{{ milestone.name }}</strong>
        <span>{{ milestone.due || 'no date' }}</span>
        <el-progress :percentage="milestone.pct" :stroke-width="8" />
        <span>{{ milestone.done }}/{{ milestone.total }}</span>
      </article>
    </el-card>

    <el-card v-if="board.drift.length" id="drift" shadow="never" class="aim-drift-card">
      <template #header>
        <span>Plan and store disagree on {{ board.drift.length }} field(s)</span>
        <RouterLink to="/plan">the plan itself</RouterLink>
      </template>
      <p class="aim-dim" style="font-size:12px;margin-top:0">
        <code class="aim-mono">plan/*.json</code> is the leader's promise; the store is what was recorded.
        A promise is not evidence, so the store wins here — and this list is what the plan still says.
      </p>
      <article v-for="(row, index) in board.drift.slice(0, 20)" :key="`${row.id}-${row.field}-${index}`"
               class="aim-attention-row">
        <TaskLink :id="row.id" />
        <strong>{{ row.field }}</strong>
        <span class="aim-dim">plan says</span>
        <span>{{ row.plan ?? '—' }}</span>
        <span class="aim-dim">store has</span>
        <span>{{ row.store ?? 'not recorded' }}<PromiseTag v-if="!row.store"
              title="Nothing recorded: this row is a plan promise the store has never seen." /></span>
      </article>
      <p v-if="board.drift.length > 20" class="aim-dim" style="font-size:12px;margin-bottom:0">
        {{ board.drift.length - 20 }} more, not drawn here.
      </p>
    </el-card>
  </section>
</template>
