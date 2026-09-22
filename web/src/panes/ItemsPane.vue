<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { listQuery } from '../composables/useTaskDrawer'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import TaskLink from '../components/TaskLink.vue'

const ctx = inject('ctx')
const board = useBoard()
const drawer = ctx.service('taskDrawer')
/**
 * `tag` is an array and `per` is the page size, and both are here rather than in
 * a second mechanism because `useQueryFilters` is the app's one rule for "the URL
 * is the state": it adopts the query whole, writes every key back, and deep-links.
 * T-0166 measured the defect this replaces (bundle at the time: `tag:""` with
 * `includes(filters.tag)`, so a second pick *replaced* the first and
 * `?tag=alpha&tag=beta` showed the union); T-0161 is why the page size is a
 * filter and not a `ref` -- a bound the reader cannot share is a bound that
 * disappears on reload.
 */
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', milestone: '', tag: [], onlyLate: false, unassigned: false,
  per: '25',
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
 * How much work nobody has taken, so the filter above is a number and not an
 * invitation to an empty list: T-0227's queue is only visible if the reader can
 * see that there is one. It is the same predicate the filter applies, over the
 * whole board, so the count and the rows it leads to cannot disagree.
 */
const unassignedCount = computed(() => board.tasks.filter(unowned).length)

/**
 * Whether this dashboard could actually run `aim task claim` for this item.
 *
 * Two halves, and both are read off the action's own command rather than
 * invented here.
 *
 * The first is the write path's declaration: a write happens at all only when
 * the server was started with `--allow-write` and says who it writes as
 * (`board.canWrite`/`board.writer`, asserted by `aimboard/cli.py:503` and
 * `:544`). No writer, no command: `claimCommand` is built from `board.writer`,
 * and a command with a hole in it is not a command.
 *
 * The second is the `--as` in the command this row would draw. The server writes
 * as one seat (`write.as`), and design/11 section 2 -- "a read can borrow a view;
 * a write cannot borrow a name" -- is why a control may name that seat only for
 * the viewer *sitting in* it. The seat is the registry's `kind` for the viewer
 * (`aimboard/api.py:109` ships `viewer_kind`), measured live as
 * `write {enabled: true, as: "human"}` while the same server reads as
 * `viewer: "claude-session1"`.
 *
 * The comparison is `writer-kind == viewer-kind` and not `=== 'human'`, which is
 * what this file shipped and what `web/tests/unassigned.spec.js` fails it on:
 * the equal-kinds form gates on the *action* -- a write may not assume a seat
 * other than the writer's -- while the literal form asserts a fact about the
 * payload (that the writer happens to be the leader) that no clause of T-0227
 * asks about. Fixtures reach this knowingly: they register `kind: 'codex'` for a
 * viewer and then write as `"human"`, and the row's *mark* is unconditional while
 * its *control* is not, so those fixtures still measure exactly the gate they
 * were written for.
 */
const sameSeat = () => {
  const writer = board.writer
  const kind = (board.doc?.agents || {})[writer]?.kind
  return Boolean(kind) && kind === board.doc?.viewer_kind
}
const claimable = (task) => Boolean(
  board.canWrite && board.writer && sameSeat() && rowCommand(task),
)

/**
 * The exact command that takes this item, or nothing at all.
 *
 * The channel is the item's own (`channel`, falling back to `context_id` for
 * records written before that field existed), because a claim names a channel and
 * the tool checks membership in it -- a command that said another channel would
 * fail the moment the reader ran it. No channel is not a channel: a board with no
 * channel to name offers no control rather than a control with a hole in it.
 *
 * `rowCommand` and not `claimCommand`, because this string is the row's *one*
 * command and T-0227 says a reader whose seat could not run it is owed the
 * command readably rather than a button they cannot press. The same function
 * decides both, so the control and the text a reader copies cannot disagree.
 */
function rowCommand(task) {
  const channel = task.channel || task.context_id || ''
  if (!channel) return ''
  return `aim task claim --as ${board.writer} --channel ${channel} --id ${task.id}`
}

/**
 * The command is a fact about the row, and it stays visible.
 *
 * `KanbanPane` shows a drag's command in a modal because a drag has nowhere else
 * to live. A control here has somewhere: the command is on the control, in the
 * DOM and on the row, so a reader can read it without clicking and a test can assert
 * the whole string rather than the presence of a button. Clicking copies it --
 * this dashboard does not write, it shows the command that does.
 */
async function copyCommand(event, task) {
  const command = rowCommand(task)
  const box = event?.currentTarget?.closest?.('tr')
  box?.querySelectorAll?.('input, textarea').forEach((field) => field.blur())
  await navigator.clipboard?.writeText(command).catch(() => {})
  ElMessage({ message: `copied: ${command}`, duration: 2000, customClass: 'aim-mono' })
}

/**
 * The row's one way in, whether the reader hit the row, its id or its title.
 *
 * One handler because the three are the same intent, and because the decisions
 * column has to be able to stop it: a click on the decisions cell that also
 * opened the drawer would put the row's action behind a modal.
 */
function openRow(row) {
  drawer.open(row.id, { tasks: board.tasks })
}

/** A link inside the row, which Element Plus still reports the row parent for. */
function activateRow(row) {
  openRow(row)
  return false
}

/**
 * One predicate for the list, the count and the pager's total.
 *
 * Written once because the three must answer the same question: a count that
 * disagreed with the list would be the second answer this project keeps finding,
 * and the pager's total disagreeing with the rows would put a page number on work
 * that does not exist.
 */
const matches = (t) => {
  const search = filters.q.toLowerCase()
  if (search && !`${t.id} ${t.title} ${t.accept || ''}`.toLowerCase().includes(search)) return false
  if (filters.owner && t.owner !== filters.owner) return false
  if (filters.status && t.status !== filters.status) return false
  if (filters.milestone && t.milestone !== filters.milestone) return false
  // T-0166: every selected tag has to be on the item. A second pick that replaced
  // the first shows the union here, which is the defect measured on the bundle
  // this replaces (`tag:""` and `includes(filters.tag)`).
  if (filters.tag.length && !filters.tag.every((tag) => (t.tags || []).includes(tag))) return false
  if (filters.onlyLate && !isOverdue(t.due, t.status, board.terminal)) return false
  if (filters.unassigned && !unowned(t)) return false
  return true
}

/** What the filters select, across the whole board. The count and the pager. */
const rows = computed(() => board.tasks.filter(matches))

/**
 * The page size, and why the bound is a filter rather than a `ref`.
 *
 * T-0161 asks for a bounded first screen on the two panes that draw one row per
 * work item, and the measurement that filed it was a page-height one (a 4,000px
 * wall of rows). A bound that lives only in component state is a bound a link
 * cannot carry and a reload forgets, so `per` is a `useQueryFilters` key exactly
 * like `tag`: same adopt-the-query-whole rule, same write-back.
 *
 * Derived from the options and never taken on trust: `?per=99999` pasted by hand
 * would otherwise unbind the page it exists to bound, and `Number('x')` is NaN
 * with a NaN slice drawn.
 */
const PAGE_SIZES = [25, 50, 100]
const perPage = computed(() => (PAGE_SIZES.includes(Number(filters.per)) ? Number(filters.per) : PAGE_SIZES[0]))

/**
 * Which slice of the filtered rows is drawn.
 *
 * Zero-based element of the URL, because `el-pagination` is the pager and that is
 * its own `current-page` contract: one authority for the number, so the control
 * and the query cannot drift by one.
 */
const page = ref(0)
const drawn = computed(() => rows.value.slice(page.value * perPage.value, (page.value + 1) * perPage.value))

/**
 * A filter change starts the reader at the top of the result.
 *
 * Without this, `?q=T-0002` with `page` left at 3 draws nothing at all: the rows
 * are there, the table looks empty, and the reader concludes there are none.
 * `per` is deliberately not a reset -- the reader changed the *size* of the
 * window, and clamping below keeps them on the same page of the same list.
 */
watch(() => [filters.q, filters.owner, filters.status, filters.milestone,
             filters.tag, filters.onlyLate, filters.unassigned], () => { page.value = 0 })

/** Clamp when the list shrinks under the reader: a page past the end draws none. */
watch([rows, perPage], () => {
  const last = Math.max(0, Math.ceil(rows.value.length / perPage.value) - 1)
  if (page.value > last) page.value = last
})

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
        <!-- T-0166: `multiple`, and the same `tag` key Kanban writes, so the
             URL carries `?tag=alpha&tag=beta` and the filter ANDs them. A
             single-value control cannot express the second pick, which is how
             the two surfaces drifted apart in the first place. -->
        <el-select v-model="filters.tag" placeholder="tag" multiple collapse-tags clearable>
          <el-option v-for="t in board.tags" :key="t" :value="t" :label="t" />
        </el-select>
        <el-checkbox v-model="filters.onlyLate">overdue only</el-checkbox>
        <!-- The app's filter mechanism, not a second one: this is the same
             `useQueryFilters` vocabulary the selects above write, so it deep-links
             as `?unassigned=1` and a reload re-reads it from the URL. -->
        <el-checkbox v-model="filters.unassigned">unassigned only</el-checkbox>
        <!-- `activeCount()` and not "fewer rows than the board holds": with a pager
             the default page already draws fewer rows than exist, so a `clear`
             offered on that count would be offered on a board with nothing to
             clear. The composable counts the keys that differ from their defaults,
             and `clear` puts exactly those back. -->
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <!-- T-0161: the bound, and it is a filter like the rest -- the number of
             rows a first screen draws lives in the URL with everything else. -->
        <el-select v-model="filters.per" size="small" placeholder="per page" data-filter="per"
                   style="width:118px">
          <el-option v-for="size in PAGE_SIZES" :key="size" :value="String(size)"
                     :label="`${size} / page`" />
        </el-select>
        <!-- The filter tally, and the pager below states the bound: one number per
             question, so neither can be read as the other. -->
        <span class="aim-filter-count">{{ rows.length }} of {{ board.tasks.length }}</span>
      </div>
    </template>

    <el-alert v-if="decisionError" type="error" :closable="false" show-icon
              title="The tool refused this action">
      <pre class="aim-mono">{{ decisionError }}</pre>
    </el-alert>
    <el-alert v-if="decisionResult" type="success" :closable="false" show-icon
              :title="decisionResult" />

    <el-table :data="drawn" size="small" max-height="66vh" style="cursor:pointer"
              @row-click="openRow" :default-sort="{ prop: 'id' }">
      <!-- T-0159: the id is a way into the work item, not a label for the row.
           `TaskLink` and not text, and not `<a>` either: a native anchor drags
           the URL onto the hash and the drawer never opens, which is the dead end
           this card is about. `activateRow` hands the click to the row's own
           handler, so id, title and row all open the same drawer. -->
      <el-table-column prop="id" label="id" width="86" sortable>
        <template #default="{ row }">
          <TaskLink :id="row.id" @click="activateRow(row)" />
        </template>
      </el-table-column>
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
      <!-- T-0161: the title is the row's second way in, and the acceptance
           sentence is clamped to two lines because one long `accept` is what made
           this list a wall -- the full text is the tooltip here and the drawer
           above, so clamping hides nothing. -->
      <el-table-column prop="title" label="title" min-width="300">
        <template #default="{ row }">
          <TaskLink :id="row.id" :label="row.title" @click="activateRow(row)" />
          <el-tooltip v-if="row.accept" :content="row.accept" placement="top" :show-after="300">
            <div class="aim-accept" :title="row.accept">{{ row.accept }}</div>
          </el-tooltip>
        </template>
      </el-table-column>
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
            <!-- One control, and only the seat that could run it gets it: see
                 `claimable`. Its text and its data-* are the command itself.
                 The other seat is shown the mark and the reason and *no command*
                 -- not a disabled button and not the string either, because the
                 string names `board.writer` and a reader handed a command that
                 writes as somebody else has been handed a command that fails.
                 `web/tests/unassigned.spec.js` measures this as the absence of
                 `[data-claim-command]` on the page, which is why the reason is
                 words rather than the command in a dimmer colour. -->
            <el-button v-if="claimable(row)" size="small" text type="primary"
                       class="aim-claim"
                       :aria-label="`Copy the command that takes ${row.id}: ${rowCommand(row)}`"
                       :data-claim-command="rowCommand(row)" :data-claim-id="row.id"
                       :data-claim-as="board.writer" :data-claim-channel="row.channel || row.context_id || ''"
                       @click.stop="copyCommand($event, row)">{{ rowCommand(row) }}</el-button>
            <span v-else class="aim-dim" style="font-size:11px"
                  title="A claim writes as one seat, and this board does not write as this viewer. A read can borrow a view; a write cannot borrow a name.">
              nobody on this seat can take it
            </span>
          </div>
          <span v-else>{{ row.owner }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="priority" width="96" sortable>
        <template #default="{ row }"><el-tag size="small" :type="PRIORITY_TYPE[row.priority] || 'info'" effect="plain">{{ row.priority }}</el-tag></template>
      </el-table-column>
      <!-- T-0159: a milestone on a row is a way into the work filed under it,
           using the same `milestone` key this pane's own filter reads, so the
           destination applies the filter it was linked with. -->
      <el-table-column prop="milestone" label="ms" width="70" sortable>
        <template #default="{ row }">
          <RouterLink v-if="row.milestone" class="aim-task-link"
                      :to="{ path: '/items', query: listQuery('milestone', row.milestone) }">
            {{ row.milestone }}
          </RouterLink>
          <span v-else class="aim-dim">—</span>
        </template>
      </el-table-column>
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

    <!-- The bound, stated rather than implied. The table's own max-height keeps a
         page inside the viewport; this is the half that says which page it is and
         how much of the list is left, and it is the reader's control for both. -->
    <el-pagination v-model:current-page="page" :page-size="perPage" :total="rows.length"
                   :pager-count="7" layout="total, prev, pager, next, jumper"
                   background class="aim-pager" />

    <!-- The queue T-0227 is about, said once as a number that leads to it. The
         count is the same predicate the checkbox filters on, so the signal and
         the list cannot disagree; at zero it is words and not a link, because a
         link to an empty list reads as work that is not there. -->
    <div class="aim-list-foot">
      <RouterLink v-if="unassignedCount" :to="{ path: '/items', query: listQuery('unassigned', '1') }"
                  class="aim-task-link" data-unassigned-signal
                  title="Work with no owner on the record: nobody has taken it.">
        {{ unassignedCount }} unassigned
      </RouterLink>
      <span v-else class="aim-dim" style="font-size:11.5px" data-unassigned-signal data-zero="1">
        0 unassigned
      </span>
    </div>
  </el-card>
</template>

<style>
/* Not scoped: `style.css` is another task's file this round, and a pager that is
   not pushed to the end of a full-width card reads as part of the table. */
.aim-pager { margin-top: 14px; justify-content: flex-end; }
/* The unassigned tally sits with the pager, one line, right-aligned: it belongs
   to the list as a whole and not to any row. */
.aim-list-foot { display: flex; justify-content: flex-end; gap: 12px; margin-top: 6px;
  font-size: 11.5px; }
/* T-0161: two lines of acceptance, no more. `-webkit-line-clamp` and not a fixed
   height, so a one-line sentence does not reserve the second line's space. */
.aim-accept { margin-top: 2px; color: var(--aim-dim); font-size: 11.5px; line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
