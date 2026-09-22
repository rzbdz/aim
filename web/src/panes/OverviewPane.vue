<script setup>
import { computed, inject, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { isPromise, useBoard } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import PhaseApprovalCard from '../components/PhaseApprovalCard.vue'
import PromiseTag from '../components/PromiseTag.vue'
import TaskLink from '../components/TaskLink.vue'

const ctx = inject('ctx')
const drawer = ctx.service('taskDrawer')
const api = ctx.service('api')
const board = useBoard()
const actionBusy = ref('')
const actionError = ref('')

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
  { label: 'Receipts owed', value: board.unacked.length, type: 'warning',
    detail: 'on the record', to: { path: '/chat', query: { needsMe: '1', shape: 'direct' } } },
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

const receiptRe = /^RECEIPT for\s+/
const recentConversations = computed(() => {
  const rows = board.conversationRows.slice(-5).reverse()
  const receipts = rows.filter((row) => receiptRe.test(row.subject || ''))
  if (receipts.length <= 1) return rows
  const first = receipts[0]
  return rows
    .filter((row) => !receiptRe.test(row.subject || '') || row === first)
    .map((row) => row === first
      ? { ...row, receiptCount: receipts.length, subject: `${receipts.length} receipts arrived` }
      : row)
})
const upcomingMilestones = computed(() => Object.values(board.milestones)
  .map((milestone) => {
    // The meter measures recorded work, like every other number here: a milestone
    // whose items are all promises is a milestone at zero, and drawing 87% of a
    // plan file as progress is the same lie as "15 overdue".
    const tasks = board.recorded.filter((task) => task.milestone === milestone.id)
    const done = tasks.filter((task) => board.terminal.includes(task.status)).length
    return { ...milestone, done, total: tasks.length,
             pct: tasks.length ? Math.round(100 * done / tasks.length) : 0 }
  })
  .filter((milestone) => milestone.total && milestone.pct < 100)
  .sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'))
  .slice(0, 3))

const clear = computed(() =>
  signals.value.every((signal) => signal.value === 0)
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
  actionError.value = ''
  const result = await api.command(argv)
  actionBusy.value = ''
  if (result.rc !== 0) {
    actionError.value = result.stderr || result.stdout || `aim exited ${result.rc}`
    return
  }
  await board.load()
}

async function confirmMessage(message) {
  await runAction('confirm', ['confirm', '--msg-id', message.msg_id, '--note', 'confirmed from attention page'])
}

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
          {{ board.unacked.length }} receipts owed
        </span>
        <span class="aim-dim" style="display:block">
          every count here is work on the record — the plan's promises are counted separately, below
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
                         :request="request" :busy="actionBusy" :error="actionError"
                         @approve="approvePhase" @reject="rejectPhase" />
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
          <RouterLink :to="{ path: '/chat', query: { thread: threadKey(message) } }" class="aim-row-link">
            {{ preview(message).slice(0, 72) }}
          </RouterLink>
          <el-tag size="small" effect="plain">{{ message.shape }}</el-tag>
          <span>{{ (message.ts || '').slice(0, 16).replace('T', ' ') }}</span>
          <el-button v-if="message.shape === 'direct' && message.ack_required && !message.acked_at"
                     size="small" :loading="actionBusy === `confirm:${message.msg_id}`"
                     @click="runAction(`confirm:${message.msg_id}`, ['confirm', '--msg-id', message.msg_id, '--note', 'confirmed from attention page'])">
            confirm receipt
          </el-button>
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
