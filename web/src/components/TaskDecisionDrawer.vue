<script setup>
import { computed, inject, ref } from 'vue'
import { useBoard } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE } from '../theme'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const ctx = inject('ctx')
const api = ctx.service('api')
const board = useBoard()
const busy = ref('')
const error = ref('')
const result = ref('')
const decisionNote = ref('')

const channels = computed(() => board.doc?.channels || [])
const channel = computed(() => {
  if (!props.task) return null
  const id = props.task.channel || props.task.context_id
  return channels.value.find((item) => item.id === id) || channels.value[0] || { id: 'hello' }
})
const taskRecorded = computed(() =>
  props.task && !(props.task.provenance || '').includes('seed'))
const isReview = computed(() => taskRecorded.value && props.task?.status === 'review')
const openBlockers = computed(() => {
  if (!props.task) return []
  return (props.task.blocked_by || []).filter((id) => {
    const blocker = board.tasks.find((task) => task.id === id)
    return !blocker || !board.terminal.includes(blocker.status)
  })
})
const events = computed(() => props.task?.events || props.task?.history || [])
const comments = computed(() => props.task?.comments || [])
const canDecide = computed(() => board.canWrite && taskRecorded.value)
const chatThread = computed(() => `ch:${channel.value?.id || 'hello'}`)

function close() {
  emit('update:modelValue', false)
}

async function run(name, argv) {
  busy.value = name
  error.value = ''
  result.value = ''
  const response = await api.command(argv)
  busy.value = ''
  if (response.rc !== 0) {
    error.value = response.stderr || response.stdout || `aim exited ${response.rc}`
    return false
  }
  result.value = (response.stdout || '').trim() || 'recorded'
  await board.load()
  return true
}

async function recordTask() {
  if (!props.task) return
  const argv = [
    'task', 'new', '--channel', channel.value.id,
    '--title', props.task.title,
    '--owner', props.task.owner || board.writer || board.viewer,
    '--status', props.task.status || 'backlog',
    '--priority', props.task.priority || 'normal',
    '--milestone', props.task.milestone || '',
    '--accept', props.task.accept || '',
  ]
  if (props.task.due) argv.push('--due', props.task.due)
  if (props.task.start) argv.push('--start', props.task.start)
  await run('record', argv)
}

async function move(status, reason = 'changed from the dashboard') {
  if (!props.task) return
  await run('move', [
    'task', 'move', '--channel', channel.value.id, '--id', props.task.id,
    '--to', status, '--reason', reason,
  ])
}

async function assignToMe() {
  if (!props.task) return
  await run('assign', [
    'task', 'assign', '--channel', channel.value.id, '--id', props.task.id,
    '--owner', board.writer || board.viewer,
  ])
}

async function publish() {
  if (!props.task) return
  await run('publish', [
    'task', 'publish', '--channel', channel.value.id, '--id', props.task.id,
    '--reason', 'published from the dashboard',
  ])
}

async function decide(decision) {
  if (!props.task) return
  if (decision !== 'approve' && !decisionNote.value.trim()) {
    error.value = `REFUSED: ${decision === 'return' ? 'requested changes' : 'rejection'} needs a reason.`
    return
  }
  const body = decision === 'approve'
    ? `Approved by the leader from the dashboard.${decisionNote.value ? ` Note: ${decisionNote.value}` : ''}`
    : `Leader decision: ${decision}. Reason: ${decisionNote.value.trim()}`
  const commented = await run('comment', [
    'task', 'comment', '--channel', channel.value.id, '--id', props.task.id,
    '--body', body,
  ])
  if (!commented) return
  if (decision === 'approve') {
    await run('decision', [
      'task', 'move', '--channel', channel.value.id, '--id', props.task.id,
      '--to', 'done', '--reason', 'approved by the leader',
    ])
  } else if (decision === 'return') {
    await run('decision', [
      'task', 'move', '--channel', channel.value.id, '--id', props.task.id,
      '--to', 'doing', '--reason', `changes requested: ${decisionNote.value.trim()}`,
    ])
  } else {
    await run('decision', [
      'task', 'move', '--channel', channel.value.id, '--id', props.task.id,
      '--to', 'dropped', '--reason', `rejected: ${decisionNote.value.trim()}`,
    ])
  }
  decisionNote.value = ''
}
</script>

<template>
  <el-drawer :model-value="modelValue" size="46%" :title="task?.id || 'Work item'"
             @update:model-value="close">
    <template v-if="task">
      <header class="aim-drawer-head">
        <div>
          <h3>{{ task.title }}</h3>
          <p>
            <el-tag size="small" effect="dark" :type="STATUS_TYPE[task.status] || 'info'">{{ task.status }}</el-tag>
            <el-tag size="small" effect="plain" :type="PRIORITY_TYPE[task.priority] || 'info'">{{ task.priority }}</el-tag>
            <span>{{ task.owner || 'unassigned' }}</span>
          </p>
        </div>
        <RouterLink :to="{ path: '/chat', query: { thread: chatThread } }">open thread</RouterLink>
      </header>

      <el-alert v-if="isReview && !task.accept" type="warning" :closable="false" show-icon
                title="This review has no acceptance condition"
                description="Request changes until the work has a sentence a reviewer can falsify." />
      <el-alert v-if="openBlockers.length" type="error" :closable="false" show-icon
                :title="`Open blockers: ${openBlockers.join(', ')}`"
                description="Done is not available until every dependency is complete." />

      <el-descriptions class="aim-drawer-details" :column="1" border size="small">
        <el-descriptions-item label="acceptance">{{ task.accept || '—' }}</el-descriptions-item>
        <el-descriptions-item label="notes">{{ task.notes || task.status_reason || task.move_reason || '—' }}</el-descriptions-item>
        <el-descriptions-item label="dates">
          {{ task.start || 'no start' }} → {{ task.due || 'no due' }}
        </el-descriptions-item>
        <el-descriptions-item label="provenance">{{ task.provenance || 'store' }}</el-descriptions-item>
      </el-descriptions>

      <section class="aim-action-panel">
        <h4>What the leader can do</h4>
        <el-alert v-if="!board.canWrite" type="info" :closable="false" show-icon
                  title="This dashboard is read-only"
                  description="Start aimboard with --allow-write to make decisions here." />

        <el-button v-if="!taskRecorded" type="primary" :disabled="!board.canWrite"
                   :loading="busy === 'record'" @click="recordTask">
          Record this work item
        </el-button>

        <template v-else-if="isReview">
          <el-input v-model="decisionNote" type="textarea" :rows="2"
                    placeholder="Decision note (required for request changes or reject)" />
          <div class="aim-decision-actions">
            <el-button type="primary" :disabled="!canDecide || Boolean(openBlockers.length)"
                       :loading="busy === 'comment' || busy === 'decision'"
                       @click="decide('approve')">
              Approve
            </el-button>
            <el-button type="warning" :disabled="!canDecide"
                       :loading="busy === 'comment' || busy === 'decision'"
                       @click="decide('return')">
              Request changes
            </el-button>
            <el-button type="danger" plain :disabled="!canDecide"
                       :loading="busy === 'comment' || busy === 'decision'"
                       @click="decide('reject')">
              Reject
            </el-button>
          </div>
        </template>

        <template v-else>
          <div class="aim-decision-actions">
            <el-button v-if="task.status === 'backlog'" :disabled="!canDecide"
                       :loading="busy === 'move'" @click="move('ready')">
              Make ready
            </el-button>
            <el-button v-if="['ready', 'blocked'].includes(task.status)" :disabled="!canDecide"
                       :loading="busy === 'move'" @click="move('doing')">
              Start doing
            </el-button>
            <el-button v-if="task.status === 'doing'" type="primary" :disabled="!canDecide"
                       :loading="busy === 'move'" @click="move('review')">
              Send to review
            </el-button>
            <el-button v-if="task.owner !== (board.writer || board.viewer)" :disabled="!canDecide"
                       :loading="busy === 'assign'" @click="assignToMe">
              Assign to me
            </el-button>
            <el-button v-if="task.visibility === 'draft'" type="warning" plain :disabled="!canDecide"
                       :loading="busy === 'publish'" @click="publish">
              Publish draft
            </el-button>
          </div>
        </template>

        <el-alert v-if="error" type="error" :closable="false" show-icon
                  title="The tool refused this action">
          <pre class="aim-mono">{{ error }}</pre>
        </el-alert>
        <el-alert v-if="result" type="success" :closable="false" show-icon :title="result" />
      </section>

      <section class="aim-drawer-record">
        <h4>Record</h4>
        <el-timeline v-if="events.length">
          <el-timeline-item v-for="(event, index) in events" :key="index"
                            :timestamp="(event.ts || event.at || '').replace('T', ' ').slice(0, 19)">
            {{ event.actor || event.by || event.author || 'unknown' }}
            {{ event.event || event.kind }}
            <span v-if="event.to">→ {{ event.to }}</span>
            <span v-if="event.owner">owner {{ event.owner }}</span>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="nothing recorded: this is still a plan seed" :image-size="60" />
        <template v-if="comments.length">
          <h5>Review comments</h5>
          <article v-for="(comment, index) in comments" :key="index" class="aim-comment">
            <strong>{{ comment.author || 'unknown' }}</strong>
            <span>{{ (comment.ts || '').replace('T', ' ').slice(0, 19) }}</span>
            <p>{{ comment.body }}</p>
          </article>
        </template>
      </section>
    </template>
  </el-drawer>
</template>
