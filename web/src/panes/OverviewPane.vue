<script setup>
import { computed, inject, ref } from 'vue'
import { useBoard } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import PhaseApprovalCard from '../components/PhaseApprovalCard.vue'
import TaskDecisionDrawer from '../components/TaskDecisionDrawer.vue'

const ctx = inject('ctx')
const api = ctx.service('api')
const board = useBoard()
const selectedTask = ref(null)
const actionDrawer = ref(false)
const actionBusy = ref('')
const actionError = ref('')

const overdue = computed(() => board.overdue)
const blocked = computed(() => board.tasks.filter((task) => task.status === 'blocked'))
const review = computed(() => board.tasks.filter((task) => task.status === 'review'))

const signals = computed(() => [
  { label: 'Overdue', value: overdue.value.length, type: 'danger',
    to: { path: '/items', query: { onlyLate: '1' } } },
  { label: 'Blocked', value: blocked.value.length, type: 'danger',
    to: { path: '/items', query: { status: 'blocked' } } },
  { label: 'Review', value: review.value.length, type: 'warning',
    to: { path: '/items', query: { status: 'review' } } },
  { label: 'Phase', value: board.phaseRequests.length, type: 'danger',
    to: { path: '/attention' } },
  { label: 'Receipts owed', value: board.unacked.length, type: 'warning',
    to: { path: '/chat', query: { needsMe: '1' } } },
])

const attentionTasks = computed(() => board.tasks
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
    const tasks = board.tasks.filter((task) => task.milestone === milestone.id)
    const done = tasks.filter((task) => board.terminal.includes(task.status)).length
    return { ...milestone, done, total: tasks.length,
             pct: tasks.length ? Math.round(100 * done / tasks.length) : 0 }
  })
  .filter((milestone) => milestone.total && milestone.pct < 100)
  .sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'))
  .slice(0, 3))

const clear = computed(() =>
  signals.value.every((signal) => signal.value === 0) && !attentionTasks.value.length)
const preview = (message) => message.subject || message.body || '(nothing yet)'
const taskRecorded = (task) => !(task.provenance || '').includes('seed')
const threadKey = (message) => {
  if (message.shape === 'channel') return `ch:${message.channel}`
  if (message.shape === 'room') return `room:${message.channel}/${message.room}`
  return `dm:${message.scope}`
}

function openTask(task) {
  selectedTask.value = task
  actionDrawer.value = true
}

function taskActionLabel(task) {
  if (!taskRecorded(task)) return 'record it'
  if (task.status === 'review') return 'accept or return'
  if (task.status === 'blocked') return 'unblock or decide'
  if (task.status === 'doing') return 'move to review'
  return 'open action'
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
      </div>
      <div>
        <RouterLink to="/items">All work items</RouterLink>
        <RouterLink to="/chat">All conversations</RouterLink>
      </div>
    </header>

    <div class="aim-attention-signals">
      <RouterLink v-for="signal in signals" :key="signal.label" :to="signal.to" class="aim-signal">
        <span>{{ signal.value }}</span>
        <strong>{{ signal.label }}</strong>
        <el-tag :type="signal.type" size="small" effect="plain">{{ signal.value ? 'needs action' : 'clear' }}</el-tag>
      </RouterLink>
    </div>

    <el-card v-if="board.phaseRequests.length" shadow="never" class="aim-phase-card">
      <template #header><span>Leader decisions</span><RouterLink to="/barrier">audit barrier</RouterLink></template>
      <PhaseApprovalCard v-for="request in board.phaseRequests"
                         :key="`${request.channel}:${request.ts}:${request.from}`"
                         :request="request" :busy="actionBusy" :error="actionError"
                         @approve="approvePhase" @reject="rejectPhase" />
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
        <el-empty v-if="!attentionTasks.length" description="no overdue, blocked, review, or high-priority doing item" :image-size="70" />
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

    <el-card shadow="never" class="aim-attention-milestones">
      <template #header><span>Next milestones</span><RouterLink to="/plan">full plan</RouterLink></template>
      <el-empty v-if="!upcomingMilestones.length" description="no unfinished milestone with tasks" :image-size="70" />
      <article v-for="milestone in upcomingMilestones" :key="milestone.id" class="aim-attention-row">
        <span class="aim-mono">{{ milestone.id }}</span>
        <strong>{{ milestone.name }}</strong>
        <span>{{ milestone.due || 'no date' }}</span>
        <el-progress :percentage="milestone.pct" :stroke-width="8" />
        <span>{{ milestone.done }}/{{ milestone.total }}</span>
      </article>
    </el-card>
  </section>

  <TaskDecisionDrawer v-model="actionDrawer" :task="selectedTask" />
</template>
