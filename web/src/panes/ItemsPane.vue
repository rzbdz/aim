<script setup>
import { computed, inject, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import TaskLink from '../components/TaskLink.vue'

const ctx = inject('ctx')
const board = useBoard()
const drawer = ctx.service('taskDrawer')
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', milestone: '', tag: '', onlyLate: false, unassigned: false,
})

/**
 * A work item belongs to nobody until someone takes it.
 *
 * The leader's rule, and the reason this predicate is here rather than a
 * `!t.owner` in the template: `""` is an owner the tool now records on purpose
 * (T-0226), so it has to be distinguishable from a payload that forgot the field
 * -- a blank owner cell and a cell that failed to render look identical, and the
 * board already draws the second one. Everything a reader gets from "unowned"
 * hangs off this one test, so the filter, the mark and the claim control cannot
 * come to disagree about which rows it is true of.
 */
const unowned = (task) => (task.owner || '') === ''

/**
 * Whether this dashboard could actually run `aim task claim` for the viewer.
 *
 * Two halves, both of them the write path's rather than a rule invented here. A
 * write happens at all only when the server was started with `--allow-write` and
 * declares the identity it writes as (`board.js` `canWrite`/`writer`, asserted by
 * `aimboard/cli.py:503` and `:544`). And the command this control carries names
 * that writer, so the one viewer it may be drawn for is the seat the server
 * writes as: design/11 section 2 -- "a read can borrow a view; a write cannot
 * borrow a name".
 *
 * That second half is about the seat the command *names*, not about a role the
 * tool would refuse. Measured, and this is the part that decides who sees it: the
 * live board is `write {enabled: true, as: "human"}` while the same server reads
 * as `viewer: "claude-session1"`. A participant is the common case here, and a
 * control drawing the participant's own name would be one whose command the tool
 * may well run -- `cmd_task_claim` only asks that the actor be a participant of
 * the channel (`bin/aim:1747`) -- while the record still says the leader wrote it.
 * `viewer_kind` is the registry's `kind` for the viewer (`aimboard/api.py:109`),
 * the payload's half that says whose seat this is. The comparison read backwards
 * -- `!== 'human'` -- hides the control from the leader and draws it for every
 * agent, which is what `web/tests/unassigned.spec.js` was written to fail on.
 */
const claimable = () => board.canWrite && board.writer
  && (board.doc?.viewer_kind || '') === 'human'

/**
 * The exact command that takes this item, or nothing at all.
 *
 * The channel is the item's own (`channel`, falling back to `context_id` for
 * records written before that field existed), because a claim names a channel and
 * the tool checks membership in it -- a command that said another channel would
 * fail the moment the reader ran it. No channel is not a channel: a board with no
 * channel to name offers no control rather than a control with a hole in it.
 */
function claimCommand(task) {
  const channel = task.channel || task.context_id || ''
  if (!channel) return ''
  return `aim task claim --as ${board.writer} --channel ${channel} --id ${task.id}`
}

/**
 * The command is a fact about the row, and it stays visible.
 *
 * `KanbanPane` shows a drag's command in a modal because a drag has nowhere else
 * to live. A button here has somewhere: the command is on the control, in the DOM
 * and on the row, so a reader can read it without clicking and a test can assert
 * the whole string rather than the presence of a button. Clicking copies it --
 * this dashboard does not write, it shows the command that does.
 */
async function copyCommand(event, task) {
  const command = claimCommand(task)
  const box = event?.currentTarget?.closest?.('tr')
  box?.querySelectorAll?.('input, textarea').forEach((field) => field.blur())
  await navigator.clipboard?.writeText(command).catch(() => {})
  ElMessage({ message: `copied: ${command}`, duration: 2000, customClass: 'aim-mono' })
}

const rows = computed(() => board.tasks.filter((t) => {
  const search = filters.q.toLowerCase()
  if (search && !`${t.id} ${t.title} ${t.accept || ''}`.toLowerCase().includes(search)) return false
  if (filters.owner && t.owner !== filters.owner) return false
  if (filters.status && t.status !== filters.status) return false
  if (filters.milestone && t.milestone !== filters.milestone) return false
  if (filters.tag && !(t.tags || []).includes(filters.tag)) return false
  if (filters.onlyLate && !isOverdue(t.due, t.status, board.terminal)) return false
  if (filters.unassigned && !unowned(t)) return false
  return true
}))

/**
 * An item needs a decision when only a person may settle it.
 *
 * design/11 §2: the surfaces that answer "what needs me" hold decisions,
 * approvals and phase requests, and every row there has an action. design/12
 * §1.3: every control carries the exact argv that resolves it, and a control
 * with no argv is a dead end. This is that rule for the work-items list: the
 * row's label names the decision rather than the bookkeeping ("inspect"), which
 * is the defect T-0176 filed.
 *
 * Two shapes qualify, and provenance is deliberately not part of the test:
 *
 *  - `review` -- someone's work is waiting on accept, request changes or reject.
 *    T-0035 is one of these and is *also* a plan seed, and the old action panel's
 *    first branch ("record this work item") is what hid the decision behind it.
 *  - a promise the plan parked on the leader: `board.promiseDecisions` is the
 *    store's one derivation (a seed whose owner is the leader and whose status is
 *    `ready`), so this asks for it rather than spelling the owner's name again.
 *    T-0004 is the row the leader pointed at.
 */
function needsDecision(task) {
  if (!task) return false
  if (task.status === 'review') return true
  return board.promiseDecisions.some((promise) => promise.id === task.id)
}

/**
 * The decisions a needs-decision row admits, in the drawer's words, each naming
 * the status it records -- except the record, which names none, because the item
 * it creates carries the promise's own status. The statuses are `bin/aim`'s own
 * vocabulary: a control that named a status the tool does not hold is a command
 * that cannot run.
 *
 * `review` gets the three from design/11 §2 (approve / request changes /
 * reject). A promise the plan parked on the leader gets the one action
 * `TaskDecisionDrawer` draws for a seed -- `Record this work item` -- and not
 * the review three: there is no work item for `task move` to act on, and
 * `web/tests/links.spec.js:181` pins the rule ("offering a decision for work
 * that has never been recorded is the control that lies"). Making a promise
 * approvable in place is T-0180's work -- import the plan and give it a record
 * -- and T-0176's own correction (channels/hello/tasks.jsonl:91) puts it out of
 * this card: "Not in scope: changing the seed behaviour, and making seed items
 * decidable." What the row owes the reader is that the record is one click and
 * not a button reading `inspect`.
 */
const DECISIONS = {
  review: [
    { key: 'approve', label: 'Approve', type: 'primary', status: 'done' },
    { key: 'return', label: 'Request changes', type: 'warning', status: 'doing', needsNote: true },
    { key: 'reject', label: 'Reject', type: 'danger', status: 'dropped', needsNote: true },
  ],
  ready: [
    { key: 'record', label: 'Record this work item', type: 'primary' },
  ],
}

/**
 * The id a `task new` is about to allocate, and the one placeholder this file
 * fills in rather than guesses.
 *
 * A plan seed has no work item, so the only verb the fabric has for it is the
 * record (T-0210 is the importer that turns a promise into one) and the record
 * allocates its own id. The decision's words are therefore addressed to the id
 * the first command prints, never to the next number counted by hand.
 */
const NEW_ID = '{new id}'

function decisionsFor(task) {
  return DECISIONS[task?.status === 'ready' ? 'ready' : 'review'] || []
}

/** Blockers that are still open, read the way the drawer reads them. */
function openBlockerIds(task) {
  return (task?.blocked_by || []).filter((id) => {
    const blocker = board.tasks.find((item) => item.id === id)
    return !blocker || !board.terminal.includes(blocker.status)
  })
}

/**
 * The exact argv one decision resolves this row with (design/12 §1.3).
 *
 * On the record, a decision is the same two events the drawer writes: the words
 * first, then the move they imply. On a promise, the decision is *what the
 * record says*: the same `task new` the drawer's `recordTask` runs, carrying the
 * promise's own status rather than a new one, and the same words follow onto the
 * id that command allocated.
 */
function decisionArgv(task, decision, note = '') {
  const channel = task.channel || task.context_id || 'hello'
  const reason = note.trim() || `decided from the work items list: ${decision.label.toLowerCase()}`
  const body = decision.key === 'record'
    ? `Recorded from the work items list: the plan's promise is now a work item.`
      + `${note.trim() ? ` Note: ${note.trim()}` : ''}`
    : decision.key === 'approve'
      ? `Approved from the work items list.${note.trim() ? ` Note: ${note.trim()}` : ''}`
      : `Decision from the work items list: ${decision.label}. Reason: ${reason}`
  const comment = ['task', 'comment', '--channel', channel, '--id', task.id, '--body', body]
  if (!isPromise(task)) {
    return [comment, ['task', 'move', '--channel', channel, '--id', task.id,
                      '--to', decision.status, '--reason', reason]]
  }
  const record = ['task', 'new', '--channel', channel, '--title', task.title,
                  '--owner', task.owner || board.writer || board.viewer,
                  '--status', task.status || 'backlog', '--priority', task.priority || 'normal',
                  '--milestone', task.milestone || '', '--accept', task.accept || '']
  if (task.start) record.push('--start', task.start)
  if (task.due) record.push('--due', task.due)
  for (const tag of task.tags || []) record.push('--tag', tag)
  return [record, comment.map((part) => (part === task.id ? NEW_ID : part))]
}

/** The command as the reader would type it: what the control's tooltip shows. */
function argvText(argv) {
  return argv.map((cmd) => `aim ${cmd.join(' ')}`).join('  &&  ')
}

/**
 * What the control says when it is hovered, including why it is unavailable.
 *
 * A disabled button with no reason is the dead end this card is about one step
 * further in: `bin/aim:1441` refuses `--to done` while a blocker is open, so the
 * reader has to be told which blocker before the click, not after it.
 */
function decisionTitle(task, decision) {
  const blockers = decision.key === 'approve' ? openBlockerIds(task) : []
  const command = argvText(decisionArgv(task, decision, notes[task.id] || ''))
  return blockers.length
    ? `${decision.label} ${task.id} — still blocked by ${blockers.join(', ')} — ${command}`
    : `${decision.label} ${task.id} — ${command}`
}

const notes = reactive({})
const decisionBusy = ref('')
const decisionError = ref('')
const decisionResult = ref('')

async function applyDecision(task, decision) {
  if (decisionBusy.value) return
  const note = (notes[task.id] || '').trim()
  if (decision.needsNote && !note) {
    decisionError.value = `REFUSED: ${decision.label.toLowerCase()} needs a reason.`
    return
  }
  const argv = decisionArgv(task, decision, note)
  decisionBusy.value = `${task.id}:${decision.key}`
  decisionError.value = ''
  decisionResult.value = ''
  const first = await ctx.service('api').command(argv[0])
  if (first.rc !== 0) {
    decisionBusy.value = ''
    decisionError.value = first.stderr || first.stdout || `aim exited ${first.rc}`
    return
  }
  let said = (first.stdout || '').trim()
  if (argv.length > 1) {
    const created = /^(\S+)\s+created\b/.exec(said)
    if (!created) {
      decisionBusy.value = ''
      decisionError.value = `${said || 'the tool said nothing'} — no id to attach the decision to`
      return
    }
    const follow = argv[1].map((part) => (part === NEW_ID ? created[1] : part))
    const second = await ctx.service('api').command(follow)
    if (second.rc !== 0) {
      decisionBusy.value = ''
      decisionError.value = `${said}\n${second.stderr || second.stdout || `aim exited ${second.rc}`}`
      return
    }
    said = `${said} · ${(second.stdout || '').trim()}`
  }
  decisionBusy.value = ''
  notes[task.id] = ''
  decisionResult.value = said
  await board.load()
}

</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="aim-filterbar">
        <el-input v-model="filters.q" placeholder="search id, title, acceptance" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filters.owner" placeholder="owner" clearable>
          <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
        </el-select>
        <el-select v-model="filters.status" placeholder="status" clearable>
          <el-option v-for="s in board.statuses" :key="s" :value="s" :label="s" />
        </el-select>
        <el-select v-model="filters.milestone" placeholder="milestone" clearable>
          <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
        </el-select>
        <el-select v-model="filters.tag" placeholder="tag" clearable>
          <el-option v-for="t in board.tags" :key="t" :value="t" :label="t" />
        </el-select>
        <el-checkbox v-model="filters.onlyLate">overdue only</el-checkbox>
        <!-- The app's filter mechanism, not a second one: this is the same
             `useQueryFilters` vocabulary the selects above write, so it deep-links
             as `?unassigned=1` and a reload re-reads it from the URL. -->
        <el-checkbox v-model="filters.unassigned">unassigned only</el-checkbox>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <span class="aim-filter-count">{{ rows.length }} of {{ board.tasks.length }}</span>
      </div>
    </template>

    <el-alert v-if="decisionError" type="error" :closable="false" show-icon
              title="The tool refused this action">
      <pre class="aim-mono">{{ decisionError }}</pre>
    </el-alert>
    <el-alert v-if="decisionResult" type="success" :closable="false" show-icon
              :title="decisionResult" />

    <el-table :data="rows" size="small" @row-click="(r) => drawer.open(r.id, { tasks: board.tasks })"
              :default-sort="{ prop: 'id' }" style="cursor:pointer">
      <el-table-column prop="id" label="id" width="86" sortable />
      <el-table-column label="action" width="278" fixed="right">
        <template #default="{ row }">
          <!-- A row that needs a decision offers the decision, and each control
               carries the exact argv it runs, so the command is readable before
               it is pressed rather than only after it fails. T-0176. -->
          <div v-if="needsDecision(row)" class="aim-row-decisions" @click.stop>
            <el-button v-for="d in decisionsFor(row)" :key="d.key" size="small"
                       :type="d.type" :plain="d.key !== 'approve'"
                       :disabled="!board.canWrite
                         || (d.key === 'approve' && openBlockerIds(row).length > 0)
                         || (d.needsNote && !(notes[row.id] || '').trim())"
                       :loading="decisionBusy === `${row.id}:${d.key}`"
                       :title="decisionTitle(row, d)"
                       :data-argv="JSON.stringify(decisionArgv(row, d, notes[row.id] || ''))"
                       :aria-label="`${d.label} ${row.id}`"
                       @click="applyDecision(row, d)">{{ d.label }}</el-button>
            <el-input v-if="decisionsFor(row).some((d) => d.needsNote)" v-model="notes[row.id]"
                      size="small" placeholder="reason (needed to request changes or reject)" />
          </div>
          <el-button v-else size="small" text :aria-label="`Inspect task ${row.id}`"
                     @click.stop="drawer.open(row.id, { tasks: board.tasks })">inspect</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="title" min-width="300" show-overflow-tooltip />
      <el-table-column prop="status" label="status" width="104" sortable>
        <template #default="{ row }"><el-tag size="small" :type="STATUS_TYPE[row.status] || 'info'" effect="dark">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="owner" label="owner" width="260" sortable>
        <template #default="{ row }">
          <!-- A blank owner cell is ambiguous to the reader: "nobody has taken
               this" and "the field did not render" draw the same nothing. So an
               owner the tool now writes as `""` is drawn as the words, and the
               row carries the one command that takes it. -->
          <div v-if="unowned(row)" class="aim-unowned">
            <el-tag size="small" type="warning" effect="plain" data-unassigned
                    title="No owner on the record: nobody has taken this work item.">unassigned</el-tag>
            <!-- One control, and only when this viewer could run it: see
                 `claimable`. Its text and its data-* are the command itself. -->
            <el-button v-if="claimable()" size="small" text type="primary"
                       class="aim-claim"
                       :aria-label="`Copy the command that takes ${row.id}: ${claimCommand(row)}`"
                       :data-claim-command="claimCommand(row)" :data-claim-id="row.id"
                       :data-claim-as="board.writer" :data-claim-channel="row.channel || row.context_id || ''"
                       @click.stop="copyCommand($event, row)">{{ claimCommand(row) }}</el-button>
            <span v-else-if="!board.writer" class="aim-dim" style="font-size:11px"
                  title="This board was started without --allow-write, so it cannot say whose name a claim would carry.">
              nobody on this seat can take it
            </span>
          </div>
          <span v-else>{{ row.owner }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="priority" width="96" sortable>
        <template #default="{ row }"><el-tag size="small" :type="PRIORITY_TYPE[row.priority] || 'info'" effect="plain">{{ row.priority }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="milestone" label="ms" width="70" sortable />
      <el-table-column prop="start" label="start" width="106" sortable />
      <el-table-column prop="due" label="due" width="118" sortable>
        <template #default="{ row }">
          <span :class="{ 'aim-late': isOverdue(row.due, row.status, board.terminal) }">
            {{ row.due || '—' }}<el-tag v-if="isOverdue(row.due, row.status, board.terminal)" size="small" type="danger" effect="plain" style="margin-left:4px">late</el-tag>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="estimate" label="est" width="66" sortable />
      <el-table-column label="blocked by" width="130">
        <template #default="{ row }">
          <!-- An id in a table is where a reader most expects to be able to go
               somewhere, so a blocker is a link into the blocker. -->
          <TaskLink v-for="b in row.blocked_by || []" :key="b" :id="b" class="aim-task-link-tag" />
          <span v-if="!(row.blocked_by || []).length" class="aim-dim">—</span>
        </template>
      </el-table-column>
      <el-table-column label="tags" min-width="150">
        <template #default="{ row }">
          <el-tag v-for="t in row.tags || []" :key="t" size="small" effect="plain" type="info" style="margin-right:3px">{{ t }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
