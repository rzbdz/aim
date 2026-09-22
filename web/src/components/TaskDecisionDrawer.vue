<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useBoard, isPromise } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE } from '../theme'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task: { type: Object, default: null },
  /**
   * How many tasks deep the reader arrived here. Following a blocker from one
   * task to another is a real path, and closing should walk back along it rather
   * than land the reader on an empty board.
   */
  depth: { type: Number, default: 1 },
})
const emit = defineEmits(['update:modelValue', 'back'])

const ctx = inject('ctx')
const api = ctx.service('api')
const drawer = ctx.service('taskDrawer')
const board = useBoard()
const busy = ref('')
const error = ref('')
const result = ref('')
const decisionNote = ref('')

/**
 * Everything typed here belongs to the item that was open when it was typed.
 *
 * This drawer is one long-lived component: the board reloads under it, a peer's
 * change swaps `props.task` for another item, and the note a reader wrote
 * against the previous item is still in the box. Clearing on the id the note was
 * typed against -- and on open and close, because a drawer reopened on the same
 * item is a new reading of it -- is the whole rule.
 */
watch(() => [props.task?.id, props.modelValue], () => {
  decisionNote.value = ''
  error.value = ''
  result.value = ''
  busy.value = ''
})

const channels = computed(() => board.doc?.channels || [])
const channel = computed(() => {
  if (!props.task) return null
  const id = props.task.channel || props.task.context_id
  return channels.value.find((item) => item.id === id) || channels.value[0] || { id: 'hello' }
})
const isPromiseItem = computed(() => isPromise(props.task))
const taskRecorded = computed(() => Boolean(props.task) && !isPromiseItem.value)

/**
 * The one action this state has, as an argv and the words for it.
 *
 * The drawer has to promise exactly what it will run: a control whose label is
 * "Approve" and whose argv is `task move --to doing` is the same class of lie as
 * a row that offers a button the panel does not contain. So the label and the
 * argv are built once, here, and the template renders this object rather than
 * deciding either one again.
 */
const action = computed(() => {
  const task = props.task
  if (!task) return null
  const head = ['--channel', channel.value?.id || 'hello', '--id', task.id]
  if (!taskRecorded.value) {
    return {
      key: 'record',
      label: 'Record this work item',
      detail: `runs: aim ${recordArgv().join(' ')} — the whole seed, as listed below`,
    }
  }
  const move = (key, label, to, reason) => {
    const argv = ['task', 'move', ...head, '--to', to, '--reason', reason]
    return { key, label, to, reason, detail: `runs: aim ${argv.join(' ')}` }
  }
  if (task.status === 'review') {
    return move('approve', 'Approve', 'done', 'approved from the dashboard')
  }
  if (task.status === 'backlog') {
    return move('move', 'Make ready', 'ready', 'made ready from the dashboard')
  }
  if (['ready', 'blocked'].includes(task.status)) {
    return move('move', 'Start doing', 'doing', 'started from the dashboard')
  }
  if (task.status === 'doing') {
    return move('move', 'Send to review', 'review', 'sent to review from the dashboard')
  }
  return null
})

/**
 * The store record this promise already has, if any.
 *
 * `task new` mints an id of the store's choosing, so the card the first click
 * made is not findable by the promise's own id. What the two clicks share is the
 * promise: a record carrying either the same id or a `recorded_from` /
 * `imported_from` that names it, or -- for the cards already recorded from a seed
 * by hand, which carry no marker at all -- the seed's title *and* its acceptance
 * sentence together. Measured live: one promise recorded three times is three
 * cards and one promise, which is why a title alone is not enough to key on but a
 * title plus the sentence the plan wrote is.
 */
const recordedAs = computed(() => {
  const task = props.task
  if (!task) return ''
  const title = (task.title || '').trim()
  const accept = (task.accept || '').trim()
  const match = board.recorded.find((row) =>
    row.id === task.id
    || row.recorded_from === task.id
    || row.imported_from === task.id
    || (title && (row.title || '').trim() === title && (row.accept || '').trim() === accept))
  return match?.id || ''
})

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
/**
 * The seed as the plan carried it, in full.
 *
 * A promise is a plan seed until someone records it, and the Record panel is
 * where the reader checks what will be written before it is. The previous
 * version showed four fields, so a seed with tags, an estimate or a dependency
 * was recorded as though it had none of them. The fields are listed rather than
 * spread so the panel keeps a stable order for a seed and a record alike.
 */
const seedFields = computed(() => {
  const task = props.task
  if (!task) return []
  const blockers = task.blocked_by || []
  const listed = [
    ['accept', task.accept],
    ['milestone', task.milestone],
    ['tags', (task.tags || []).join(', ')],
    ['estimate', task.estimate_pts || task.estimate],
    ['start', task.start],
    ['due', task.due],
    ['priority', task.priority],
    ['blocked by', blockers.length > 1
      // `task new` takes one, so the panel says which one the argv carries
      // rather than leaving the reader to find out from the record later.
      ? `${blockers.join(', ')} (only ${blockers[0]} is written by \`task new\`)`
      : blockers.join(', ')],
    ['provenance', task.provenance],
  ]
  return listed.map(([label, value]) => ({
    label,
    value: value === 0 || value ? String(value) : '—',
  }))
})
const chatThread = computed(() => `ch:${channel.value?.id || 'hello'}`)

function close() {
  emit('update:modelValue', false)
}

/** Follow a blocker, resolving it against the board as it is now. */
function openBlocker(id) {
  drawer.open(id, { tasks: board.tasks })
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

/**
 * The exact argv this drawer's Record runs, and the whole seed it carries.
 *
 * Every field the plan put on the promise is written, because a seed recorded
 * without its tags, estimate or dependency is a promise the store now holds in a
 * weaker form than the plan did. `--estimate` takes points and the store records
 * 0 for "not estimated", so a seed without one is still passed explicitly.
 */
function recordArgv() {
  const task = props.task
  const argv = [
    'task', 'new', '--channel', channel.value.id,
    '--title', task.title,
    '--owner', task.owner || board.writer || board.viewer,
    '--status', task.status || 'backlog',
    '--priority', task.priority || 'normal',
    '--milestone', task.milestone || '',
    '--accept', task.accept || '',
    '--estimate', String(task.estimate_pts || task.estimate || 0),
  ]
  if (task.start) argv.push('--start', task.start)
  if (task.due) argv.push('--due', task.due)
  for (const tag of task.tags || []) argv.push('--tag', tag)
  const blockers = task.blocked_by || []
  if (blockers.length) {
    // `task new` takes one `--blocked-by`; a seed with two is recorded with the
    // first and the rest named in the panel, rather than silently dropped.
    argv.push('--blocked-by', blockers[0])
  }
  // Nothing to append for the promise's own id: `task new` mints one and has no
  // flag to carry a foreign id. The guard that refuses the second click is
  // `recordedAs`, which reads the board rather than a flag the record does not
  // have, so the id being absent from the argv is not a field lost on the way in.
  return argv
}

async function recordTask() {
  if (!props.task) return
  const existing = recordedAs.value
  if (existing) {
    // Refuse in place rather than navigate: an id the reader can read and use is
    // the whole message, and walking to the card would hide the refusal behind a
    // second render of a different item.
    result.value = `${props.task.id} is already recorded as ${existing} — nothing created.`
    return
  }
  await run('record', recordArgv())
}

/** `move`, with the argv it will run stated before it runs. */
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
          <el-button v-if="depth > 1" size="small" text @click="emit('back')">
            <el-icon><Back /></el-icon> previous task
          </el-button>
          <h3>{{ task.title }}</h3>
          <p>
            <el-tag size="small" effect="dark" :type="STATUS_TYPE[task.status] || 'info'">{{ task.status }}</el-tag>
            <el-tag size="small" effect="plain" :type="PRIORITY_TYPE[task.priority] || 'info'">{{ task.priority }}</el-tag>
            <span>{{ task.owner || 'unassigned' }}</span>
          </p>
        </div>
        <RouterLink :to="{ path: '/chat', query: { thread: chatThread } }">open thread</RouterLink>
      </header>

      <el-alert v-if="taskRecorded && task.status === 'review' && !task.accept" type="warning" :closable="false" show-icon
                title="This review has no acceptance condition"
                description="Request changes until the work has a sentence a reviewer can falsify." />
      <el-alert v-if="openBlockers.length" type="error" :closable="false" show-icon
                description="Done is not available until every dependency is complete.">
        <template #title>
          Open blockers:
          <!-- A blocker id is a fact about another work item, so it is a way in to
               it. Asking the board for the id at click time means the drawer shows
               the blocker's *current* state, not a copy from whenever this alert
               was drawn. -->
          <el-button v-for="id in openBlockers" :key="id" size="small" text type="danger"
                     class="aim-blocker-link" @click="openBlocker(id)">{{ id }}</el-button>
        </template>
      </el-alert>

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

        <el-alert v-if="isPromiseItem" type="info" :closable="false" show-icon
                  title="This is a plan seed, not recorded work"
                  description="Nothing has happened to it: it has no events and no owner on the record. Record it to give it a card, or leave it as a promise." />

        <el-button v-if="!taskRecorded" type="primary" :disabled="!board.canWrite"
                   :loading="busy === 'record'"
                   :title="recordArgv().join(' ')" @click="recordTask">
          Record this work item
        </el-button>
        <p v-if="!taskRecorded" class="aim-action-detail">{{ action.detail }}</p>
        <el-alert v-if="!taskRecorded && recordedAs" type="warning" :closable="false" show-icon
                  :title="`Already recorded as ${recordedAs}`"
                  description="Record is refused; the existing card is what this promise became." />

        <template v-else-if="task.status === 'review'">
          <el-input v-model="decisionNote" type="textarea" :rows="2"
                    placeholder="Decision note (required for request changes or reject)" />
          <p class="aim-action-detail">
            Approve runs: aim task move --channel {{ channel?.id || 'hello' }} --id {{ task.id }}
            --to done --reason approved from the dashboard
          </p>
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
            <el-button v-if="action" :type="action.key === 'move' ? 'primary' : 'default'"
                       :disabled="!canDecide"
                       :loading="busy === 'move'"
                       :title="action.detail" @click="move(action.to, action.reason)">
              {{ action.label }}
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
          <p v-if="action" class="aim-action-detail">{{ action.detail }}</p>
        </template>

        <el-alert v-if="error" type="error" :closable="false" show-icon
                  title="The tool refused this action">
          <pre class="aim-mono">{{ error }}</pre>
        </el-alert>
        <el-alert v-if="result" type="success" :closable="false" show-icon :title="result" />
      </section>

      <section class="aim-drawer-record">
        <h4>{{ taskRecorded ? 'Record' : 'The seed, whole' }}</h4>
        <!-- Every field the plan carried, not a summary of it: this is what
             Record writes, and a reader checking the box before the click is
             reading the argv rather than a description of it. -->
        <el-descriptions class="aim-seed-fields" :column="1" border size="small">
          <el-descriptions-item v-for="field in seedFields" :key="field.label" :label="field.label">
            {{ field.value }}
          </el-descriptions-item>
        </el-descriptions>
        <p v-if="!taskRecorded" class="aim-action-detail">
          Recording runs: aim {{ recordArgv().join(' ') }}
        </p>
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
