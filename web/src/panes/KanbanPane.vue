<script setup>
import { computed, inject, ref } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { isOverdue } from '../theme'
import StatusTag from '../components/StatusTag.vue'
import OwnerAvatar from '../components/OwnerAvatar.vue'

const ctx = inject('ctx')
const board = useBoard()
// The shell owns the drawer; this pane only says what to open. See useTaskDrawer.
const drawer = ctx.service('taskDrawer')
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', milestone: '', tag: [], priority: '', onlyLate: false, unassigned: false,
})
const compact = ref(false)

/**
 * The same predicate Items draws, and the same one the filter reads, for the same
 * reason `isOverdue` lives in the store: a card that says "unassigned" and a
 * filter that claims to show unassigned rows have to be one question asked once.
 */
const unowned = (t) => (t.owner || '') === ''

/**
 * Whether this dashboard could actually run `aim task claim` for the viewer.
 *
 * `board.canWrite`/`board.writer` are the write path's own declarations
 * (`aimboard/cli.py:503` refuses the POST without `--allow-write`, `:594` is the
 * only place `write.as` is set), and the figure is drawn for one seat only: the
 * seat the server writes as. `design/11` section 2 -- "a read can borrow a view; a
 * write cannot borrow a name" -- so a control naming `board.writer` may only be
 * offered to the viewer whose own kind is that writer's.
 *
 * Measured, and it is the seat rather than a role that decides this: the live
 * board is `write {enabled: true, as: "human"}` while it reads as `viewer:
 * "claude-session1"`. A participant is the common case, and the tool would run a
 * claim drawing the participant's own name -- `cmd_task_claim` asks only that the
 * actor be a participant of the channel (`bin/aim:1747`) -- while the record still
 * says the leader took the card. This pane must draw exactly the figure the
 * work-items list and the attention queue draw; two surfaces disagreeing about who
 * may claim is the second implementation this task is about.
 */
const claimable = (t) => board.canWrite && board.writer
  && (board.doc?.viewer_kind || '') === 'human'

/** The item's own channel: `aim task claim` checks membership in the one it names. */
function claimCommand(t) {
  const channel = t.channel || t.context_id || ''
  if (!channel) return ''
  return `aim task claim --as ${board.writer} --channel ${channel} --id ${t.id}`
}

const visible = (t) => {
  const search = filters.q.toLowerCase()
  if (search && !`${t.id} ${t.title} ${t.accept || ''}`.toLowerCase().includes(search)) return false
  if (filters.owner && t.owner !== filters.owner) return false
  if (filters.milestone && t.milestone !== filters.milestone) return false
  if ((filters.tag || []).length && !(filters.tag || []).every((tag) => (t.tags || []).includes(tag))) return false
  if (filters.priority && t.priority !== filters.priority) return false
  if (filters.onlyLate && !isOverdue(t.due, t.status, board.terminal)) return false
  if (filters.unassigned && !unowned(t)) return false
  return true
}

/**
 * The columns are what the board has, narrowed - never what the filter says.
 *
 * `board.byStatus` is the fold of the log, so a status with no work items is a
 * status the board drew and the filter hid, not a column that stopped existing.
 * Deriving the column list from the present tasks instead would make the filter
 * count disagree with the column headers, which is how a board starts lying.
 */
const cols = computed(() => {
  const next = {}
  for (const status of board.statuses) next[status] = (board.byStatus[status] || []).filter(visible)
  return next
})

/**
 * The board is read-only, and dragging is how you find that out.
 *
 * A drag is a real intention, so it is not swallowed: it becomes the exact
 * command that would carry it out. The alternative - a drag that writes - is the
 * second implementation of the write discipline (design/05 D6); the alternative -
 * a drag that silently snaps back - teaches the reader that the board is broken.
 *
 * Callers pass a *copy* of the column, because `vue-draggable-plus` falls back
 * to mutating its `modelValue` array in place when the model refuses the write.
 * Mutating `cols.value[status]` would edit a computed's value behind its back and
 * leave every later recompute working from a filtered list that had drifted.
 */
async function onMoved(evt, status) {
  if (!evt.item || (status && evt.from?.dataset?.status !== status)) return
  const id = evt.item.dataset?.id
  const to = evt.to?.dataset?.status
  const from = evt.from?.dataset?.status
  if (!id || !to || to === from) return
  const task = board.tasks.find((item) => item.id === id)
  const channel = task?.channel || task?.context_id || board.channels[0]?.id || 'hello'
  // `board.writer`, never `board.viewer`: a write is the server's identity to
  // assert (design/06 R1), and the two differ on the live board -- it reads as
  // `claude-session1` while it writes as `human`. `|| board.viewer` was the
  // fallback for an empty writer, which the same server never produces: it
  // declares `write.as` exactly when `--allow-write` is set.
  const command = `aim task move --as ${board.writer} --channel ${channel} --id ${id} --to ${to}`
  await ElMessageBox.alert(command, `${id} — the dashboard does not write`, {
    confirmButtonText: 'copy the command', showCancelButton: true, cancelButtonText: 'close',
    customClass: 'aim-mono',
  }).then(() => navigator.clipboard?.writeText(command)).catch(() => {})
}

/**
 * Copy the claim command, exactly as the card shows it.
 *
 * The board does not claim the item: it hands the reader the one command that
 * does, which is the same discipline the refused drag above keeps. The clipboard
 * is a convenience, so a refusal to write it is swallowed -- the string is on the
 * card either way, and the message is the same whether or not the copy landed.
 */
async function copyClaim(event, task) {
  const command = claimCommand(task)
  event?.currentTarget?.blur?.()
  await navigator.clipboard?.writeText(command).catch(() => {})
  ElMessage({ message: `copied: ${command}`, duration: 2000, customClass: 'aim-mono' })
}

const shipped = computed(() => Object.values(cols.value).flat().length)

/** Resolved against the board at click time, so the drawer shows the current
 *  state of the task rather than the copy this column was rendered from. */
function openTask(task) {
  drawer.open(task.id, { tasks: board.tasks })
}
</script>

<template>
  <div class="aim-filterbar">
    <el-input v-model="filters.q" size="small" placeholder="search tasks" clearable data-filter="q">
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>
    <el-select v-model="filters.owner" size="small" placeholder="any owner" clearable data-filter="owner">
      <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
    </el-select>
    <el-select v-model="filters.milestone" size="small" placeholder="any milestone" clearable data-filter="milestone">
      <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
    </el-select>
    <el-select v-model="filters.tag" size="small" placeholder="any tag" multiple collapse-tags clearable data-filter="tag">
      <el-option v-for="tag in board.tags" :key="tag" :value="tag" :label="tag" />
    </el-select>
    <el-select v-model="filters.priority" size="small" placeholder="any priority" clearable data-filter="priority">
      <el-option v-for="priority in board.priorities" :key="priority" :value="priority" :label="priority" />
    </el-select>
    <el-checkbox v-model="filters.onlyLate" size="small">overdue only</el-checkbox>
    <el-checkbox v-model="filters.unassigned" size="small" data-filter="unassigned">unassigned only</el-checkbox>
    <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
    <span class="aim-filter-count">{{ shipped }} of {{ board.tasks.length }}</span>
    <el-checkbox v-model="compact" size="small">compact</el-checkbox>
    <span class="aim-filter-count" style="margin-left:auto">
      {{ board.withheld ? `${board.withheld} withheld · ` : '' }}drag shows the command, it does not write
    </span>
  </div>

  <div class="aim-board">
    <section v-for="st in board.statuses" :key="st" class="aim-col">
      <header>
        <StatusTag :status="st" />
        <span class="aim-count">{{ (cols[st] || []).length }}</span>
      </header>
      <VueDraggable :model-value="cols[st] || []" :group="{ name: 'tasks' }" :data-status="st"
                    class="aim-colbody" :animation="140" @end="onMoved($event, st)">
        <article v-for="t in cols[st] || []" :key="t.id" class="aim-card aim-clickable" :data-id="t.id"
                 role="button" tabindex="0" :aria-label="`Open task ${t.id}: ${t.title}`"
                 @click="openTask(t)"
                 @keydown.enter.prevent="openTask(t)"
                 @keydown.space.prevent="openTask(t)">
          <div style="display:flex;align-items:baseline;gap:8px">
            <span class="aim-id">{{ t.id }}</span>
            <span style="flex:1" />
            <el-button size="small" text @click.stop="openTask(t)">inspect</el-button>
            <span v-if="t.estimate" class="aim-id">{{ t.estimate }}d</span>
          </div>
          <span class="aim-title">{{ t.title }}</span>
          <!-- Unowned is drawn in words, on the card, where "nobody has taken
               this" is the reader's first question: an avatar with no name beside
               it is the blank cell this replaces. -->
          <div v-if="unowned(t)" class="aim-unowned">
            <el-tag size="small" type="warning" effect="plain" data-unassigned
                    title="No owner on the record: nobody has taken this work item.">unassigned</el-tag>
            <el-button v-if="claimable(t)" size="small" text type="primary" class="aim-claim"
                       :aria-label="`Copy the command that takes ${t.id}: ${claimCommand(t)}`"
                       :data-claim-command="claimCommand(t)" :data-claim-id="t.id"
                       :data-claim-as="board.writer" :data-claim-channel="t.channel || t.context_id || ''"
                       @click.stop="copyClaim($event, t)">{{ claimCommand(t) }}</el-button>
          </div>
          <template v-if="!compact">
            <div v-if="t.accept" class="aim-accept">
              <el-icon style="margin-top:2px"><Aim /></el-icon><span>{{ t.accept }}</span>
            </div>
          </template>
          <div class="aim-meta">
            <OwnerAvatar :id="t.owner" :size="18" />
            <span v-if="t.due" :class="{ 'aim-late': isOverdue(t.due, t.status, board.terminal) }">
              {{ t.due.slice(5) }}{{ isOverdue(t.due, t.status, board.terminal) ? ' late' : '' }}
            </span>
            <span v-if="t.milestone">{{ t.milestone }}</span>
            <template v-for="b in t.blocked_by || []" :key="b">
              <span class="aim-flag blocked"><el-icon><Lock /></el-icon>{{ b }}</span>
            </template>
            <span v-if="t.priority" class="aim-flag"
                  :style="{ color: t.priority === 'high' ? 'var(--aim-danger)' : 'inherit' }">
              <el-icon><Top v-if="t.priority === 'high'" /><Bottom v-else /></el-icon>{{ t.priority }}
            </span>
          </div>
          <div v-if="(t.tags || []).length || t.visibility === 'draft' || (t.provenance || '').includes('seed')"
               style="display:flex;gap:5px;flex-wrap:wrap;margin-top:8px">
            <span v-if="(t.provenance || '').includes('seed')" class="aim-chip seed">plan seed</span>
            <span v-if="t.visibility === 'draft'" class="aim-chip draft">draft</span>
            <span v-for="g in (t.tags || []).slice(0, 4)" :key="g" class="aim-chip">{{ g }}</span>
          </div>
        </article>
      </VueDraggable>
    </section>
  </div>
</template>
