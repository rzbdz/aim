<script setup>
import { computed, inject, ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { isOverdue } from '../theme'
import StatusTag from '../components/StatusTag.vue'
import OwnerAvatar from '../components/OwnerAvatar.vue'
import TaskLink from '../components/TaskLink.vue'
import PromiseTag from '../components/PromiseTag.vue'

const ctx = inject('ctx')
const board = useBoard()
// The shell owns the drawer; this pane only says what to open. See useTaskDrawer.
const drawer = ctx.service('taskDrawer')
const api = ctx.service('api')
/** Named, because `clear` and the per-chip reset off the template both have to
 *  restore the same set: a reset that invents its own empty value is a second
 *  answer to "what is this filter when it is off". */
const DEFAULTS = {
  q: '', owner: '', milestone: '', tag: [], priority: '', onlyLate: false, unassigned: false,
  per: '25',
}
const { filters, clear } = useQueryFilters(DEFAULTS)

/**
 * Whether any *question* is on, so "clear" is drawn only then.
 *
 * Not the composable's `activeCount`, which counts `per` as well: a page size
 * always holds a value, so that count is never zero and the button would be drawn
 * on an untouched board. A page size is a window, not a filter.
 */
const asked = computed(() => Object.keys(DEFAULTS)
  .filter((key) => key !== 'per')
  .some((key) => JSON.stringify(filters[key]) !== JSON.stringify(DEFAULTS[key])))

/**
 * T-0161 clause 3: the card is bounded by default, and the whole acceptance
 * lives in the drawer.
 *
 * Measured on the live board before this (87 cards, acceptances of one to three
 * sentences): every card drew its whole acceptance, so the column body was a wall
 * of prose and the reader scrolled past the cards to find the cards. So the bound
 * is the default -- three lines of acceptance, set in the style block below --
 * and the drawer, which already holds the whole item, is where the rest is read.
 *
 * `compact` is one step further: no acceptance at all. It defaulted to the bound
 * itself while the bound was opt-in, which made the reader ask for the thing the
 * card asks for; as "draw less than the bound" it is the reader's choice, and it
 * starts off.
 */
const compact = ref(false)

/** The card whose claim is in flight, so the control can say it is working and
 *  a second click cannot send the same claim twice. */
const claimBusy = ref('')

/**
 * The same predicate Items draws, and the same one the filter reads, for the same
 * reason `isOverdue` lives in the store: a card that says "unassigned" and a
 * filter that claims to show unassigned rows have to be one question asked once.
 */
const unowned = (t) => (t.owner || '') === ''

/**
 * Whether this dashboard could actually run `aim task claim` for this card.
 *
 * `board.canWrite`/`board.writer` are the write path's own declarations
 * (`aimboard/cli.py:503` refuses the POST without `--allow-write`, `:594` is the
 * only place `write.as` is set), so no writer means no command and no control.
 * `design/11` section 2 -- "a read can borrow a view; a write cannot borrow a
 * name" -- is the other half: the command names the seat the server writes as, so
 * it may be offered only to the viewer *in* that seat.
 *
 * The seat is the registry's `kind` for the writer compared with the registry's
 * `kind` for the viewer, not the literal `'human'` this pane used to test. The
 * literal asserted a fact about the payload -- that the server's writer happens to
 * be the leader -- which decides nothing about whether the *action* is the
 * reader's; the equal-kinds form is the write rule itself. Measured live the two
 * differ in name but not in kind (`write.as: "human"` while `viewer:
 * "claude-session1"`, both `kind: 'human'`/absent), which is why the literal
 * looked right on the live board and wrong on every fixture.
 *
 * This pane must draw exactly the figure the work-items list draws; two surfaces
 * disagreeing about who may claim is the second implementation this task is about.
 * Both read the item's own command as well (`claimCommand` is `''` for an item
 * with no channel), so an item that cannot be claimed has no control anywhere.
 */
const sameSeat = () => {
  const writer = board.writer
  const kind = (board.doc?.agents || {})[writer]?.kind
  return Boolean(kind) && kind === board.doc?.viewer_kind
}
const claimable = (t) => Boolean(
  board.canWrite && board.writer && sameSeat() && claimCommand(t),
)

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
 *
 * T-0161 bounds the *page* rather than the column, and it has to be one window
 * over all of them: bounding each column separately would draw up to
 * `statuses x per` cards and call that a page. So the cards that pass the filter
 * are ranked once (the board's status order, and each column's own order from
 * `byStatus`) and every column draws its slice of that one window.
 */
const PAGE_SIZES = [25, 50, 100]

/**
 * Derived from the options and never taken on trust: `?per=99999` pasted by hand
 * would otherwise unbind the page it is supposed to bound, and `Number('')` is 0,
 * which would draw nothing at all.
 */
const per = computed(() => (PAGE_SIZES.includes(Number(filters.per)) ? Number(filters.per) : PAGE_SIZES[0]))

/**
 * Ownership as one control, backed by two filters.
 *
 * "any owner" is the absence of both, so the three states are mutually exclusive
 * and the picker cannot draw a combination the filter does not have. `?unassigned=1`
 * is a documented deep link (T-0227) and reads here as "unowned only" -- which is
 * the state the board used to render as a blank owner cell nobody could name.
 *
 * It has to be a *select* and not a checkbox: a checkbox whose model is derived
 * discards the click on the next render, so it would flip back under the reader's
 * cursor. The owner options are the same three the old select drew, plus the one
 * that answers "nobody has taken this".
 */
const OWNER_ANY = '__any__'
const OWNER_UNOWNED = '__unowned__'
const ownerScope = computed({
  get() {
    // A named owner is shown as itself: answering "has an owner" to a picker that
    // says `codex` would hide which one the board is filtered to.
    if (filters.owner) return filters.owner
    return filters.unassigned ? OWNER_UNOWNED : OWNER_ANY
  },
  set(scope) {
    filters.unassigned = scope === OWNER_UNOWNED
    filters.owner = scope === OWNER_UNOWNED || scope === OWNER_ANY ? '' : scope
  },
})

/** Zero-based element of the URL, because `el-pagination` is the pager and that
 *  is its own `current-page` contract: one authority for the number. */
const page = ref(0)

/** What the filters select, before the page bound: the pager's total. */
const matched = computed(() => board.tasks.filter(visible).length)

/**
 * A column header's number, in the two universes that number can mean.
 *
 * The badge was `(cols[st] || []).length`, and that was wrong twice over. It is
 * the count of *cards drawn on this page* (`cols` is sliced by the page bound at
 * `:226-236`), so a column of ninety with `per=25` said 25; and the set it
 * counted is the merge, so the `done` column's number carried promises whose only
 * evidence is `plan/plan.json`. Measured on this tree
 * (`fabric.load_fabric(root, ['plan/*.json'], date(2026,9,22))`, 177 rows): 87
 * promises, 72 of them `status: done` in the plan file and 15 `dropped`, and a
 * seed has no events at all -- against 90 recorded rows whose `done` is 67. So
 * the `done` column read a number that was the plan file's arithmetic beside a
 * status tag, in a column whose cards the reader counts as work.
 *
 * The split is drawn the way every other two-universe number on this board is
 * drawn: the record first and named (`on the record`), the promise half beside
 * it and named (`planned`), which is `GanttPane`'s header idiom and the reason
 * `PromiseTag` prints a word rather than only a hue -- a reader who cannot see
 * the colour still reads which half they are looking at.
 *
 * Both numbers are over `visible` (the filter the reader set) and **not** over
 * `cols`, which is the page as well. A bound stated in a column header would be
 * the bound drawn once per column, and worse here: `visible` is this method's own
 * predicate rather than a computed, so the two numbers cannot be read as "of a
 * total" -- the column is bounded and `GanttPane.vue:634-637` is the pane that
 * states a window (`N shown`, `of M dated`) because its chart is bounded by
 * height. That is the same choice `ItemsPane.vue:457` makes (`{{ rows.length }}
 * of {{ board.tasks.length }}` -- membership over the merge, the page stated by
 * the pager below), with this pane's own two halves named and the pager's own
 * numbers left to the pager (`:490-492`).
 *
 * The two halves are published as one number and one clause on purpose, rather
 * than handed to `StatusTag`'s `count` prop: that prop draws a bare number beside
 * the status name, which is exactly the shape that cannot say which universe it
 * counted. `components/StatusTag.vue:10` has nothing passing it today, and the
 * fix here is the sentence, not the slot.
 */
const colCounts = computed(() => {
  const next = {}
  for (const status of board.statuses) {
    const all = (board.byStatus[status] || []).filter(visible)
    const promises = all.filter(isPromise).length
    next[status] = { promises, recorded: all.length - promises }
  }
  return next
})
/** One column's pair, so the template reads one object per header rather than a
 *  fallback per clause -- the two numbers have to come from the same fold. */
const colCount = (status) => colCounts.value[status] || { promises: 0, recorded: 0 }

const cols = computed(() => {
  const next = {}
  let seen = 0
  for (const status of board.statuses) {
    const all = (board.byStatus[status] || []).filter(visible)
    const from = Math.max(0, page.value * per.value - seen)
    next[status] = all.slice(from, from + per.value)
    seen += all.length
  }
  return next
})

/**
 * A filter change starts the reader on the first page of the new result.
 *
 * `per` is deliberately not among them: the reader changed the *size* of the
 * window, not the question, and the clamp below keeps them on the same page of the
 * same list. Without the clamp a page past the end draws no cards at all, which a
 * reader cannot tell from "there are none".
 */
watch(() => [filters.q, filters.owner, filters.milestone, filters.tag, filters.priority,
             filters.onlyLate, filters.unassigned], () => { page.value = 0 })
watch([matched, per], () => {
  const last = Math.max(0, Math.ceil(matched.value / per.value) - 1)
  if (page.value > last) page.value = last
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
 * Take the work item, from the card, when this dashboard is allowed to act.
 *
 * T-0227's acceptance is the command, and the same one the card copies when the
 * page cannot write -- so the string on the control is the string that ran, and a
 * `claim` the tool refuses (the channel membership check in `bin/aim`) comes back
 * verbatim instead of being softened into "could not". A claim is an append, not
 * a copy, so unlike the clipboard above a refusal is *not* swallowed here.
 *
 * The board is re-read after it lands, because the card that just stopped being
 * unowned is the evidence the claim happened.
 */
async function applyClaim(task) {
  const command = claimCommand(task)
  if (!command || claimBusy.value) return
  claimBusy.value = task.id
  const response = await api.command(command.split(' '))
  const said = (response.stdout || response.stderr || '').trim()
  if (response.rc === 0) {
    ElMessage({ message: said || `claimed ${task.id}`, duration: 2500, customClass: 'aim-mono' })
    await board.load()
  } else {
    ElMessage({ message: `REFUSED: ${said || `aim exited ${response.rc}`}`, type: 'error', duration: 6000 })
  }
  claimBusy.value = ''
}

/**
 * Drop one tag from the array, without `el-select`'s own clear.
 *
 * The array is what the URL repeats, and the picker draws two of them as one chip
 * plus `+ 1`, so the second tag has no control of its own: without this the reader
 * can only reset *every* tag, which is the wrong answer when they picked one too
 * many. It is the same `filters.tag` the URL write loop watches, so the removal
 * round-trips like any other change.
 */
function removeTag(tag) {
  filters.tag = filters.tag.filter((item) => item !== tag)
}

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
    <!-- T-0227: the unowned half of ownership is reachable from the UI, not only
         from a pasted `?unassigned=1`. -->
    <el-select v-model="ownerScope" size="small" placeholder="any owner" data-filter="owner"
               style="width:210px">
      <el-option :value="OWNER_ANY" label="any owner" />
      <el-option :value="OWNER_UNOWNED" label="unassigned only" data-filter="unassigned" />
      <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
    </el-select>
    <el-select v-model="filters.milestone" size="small" placeholder="any milestone" clearable data-filter="milestone"
               style="width:186px">
      <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
    </el-select>
    <el-select v-model="filters.tag" size="small" placeholder="any tag" multiple collapse-tags clearable data-filter="tag">
      <el-option v-for="tag in board.tags" :key="tag" :value="tag" :label="tag" />
    </el-select>
    <el-select v-model="filters.priority" size="small" placeholder="any priority" clearable data-filter="priority">
      <el-option v-for="priority in board.priorities" :key="priority" :value="priority" :label="priority" />
    </el-select>
    <el-checkbox v-model="filters.onlyLate" size="small">overdue only</el-checkbox>
    <el-button v-if="asked" size="small" text @click="clear()">clear</el-button>
    <span class="aim-filter-count">{{ matched }} of {{ board.tasks.length }}</span>
    <!-- T-0161: the bound is a filter like the rest, so a link carries the page
         size with the query it was taken under. -->
    <el-select v-model="filters.per" size="small" placeholder="per page" data-filter="per"
               style="width:118px">
      <el-option v-for="size in PAGE_SIZES" :key="size" :value="String(size)" :label="`${size} / page`" />
    </el-select>
    <el-checkbox v-model="compact" size="small">hide acceptance</el-checkbox>
    <span class="aim-filter-count" style="margin-left:auto">
      {{ board.withheld ? `${board.withheld} withheld · ` : '' }}drag shows the command, it does not write
    </span>
  </div>

  <!-- T-0166: the selected tags as chips, each removable on its own. The picker
       collapses two tags into one chip and `+ 1`, so the second tag would have no
       control anywhere. -->
  <div v-if="filters.tag.length" class="aim-tagrow">
    <span class="aim-filter-count">tags (all of):</span>
    <el-tag v-for="tag in filters.tag" :key="tag" size="small" closable type="info" effect="plain"
            :data-tag="tag" title="Remove this tag from the filter"
            @close="removeTag(tag)">{{ tag }}</el-tag>
  </div>

  <div class="aim-board">
    <section v-for="st in board.statuses" :key="st" class="aim-col">
      <header>
        <StatusTag :status="st" />
        <!-- The two halves of this column, named (`colCounts`, `:177-224`). The
             second clause is drawn only when the column holds one: `0 planned` on
             the other five is a number about a set that is empty, in a header
             whose whole job is to say how much is in the column, and the absence
             already says it. It is the same asymmetry `GanttPane.vue:721-727`
             keeps for its undated split -- and the reason `data-promises="0"` is
             published here where the visual clause is not, so a test can ask the
             count the screen declines to print. -->
        <span class="aim-count" data-recorded>
          {{ colCount(st).recorded }} on the record<span
            v-if="colCount(st).promises" class="aim-dim" data-promises>
            · {{ colCount(st).promises }} planned</span>
        </span>
      </header>
      <VueDraggable :model-value="cols[st] || []" :group="{ name: 'tasks' }" :data-status="st"
                    class="aim-colbody" :animation="140" @end="onMoved($event, st)">
        <article v-for="t in cols[st] || []" :key="t.id" class="aim-card aim-clickable" :data-id="t.id"
                 role="button" tabindex="0" :aria-label="`Open task ${t.id}: ${t.title}`"
                 @click="openTask(t)"
                 @keydown.enter.prevent="openTask(t)"
                 @keydown.space.prevent="openTask(t)">
          <div style="display:flex;align-items:baseline;gap:8px">
            <!-- T-0227: an id that is dead text is the failure TaskLink exists to
                 stop, and the card's own header is where the reader asks for it. -->
            <TaskLink :id="t.id" class="aim-id" />
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
            <!-- The same two halves the work-items row draws, and the same choice
                 about what the other seat is shown: the mark and a reason, never
                 the command. `aim task claim --as <writer>` names the seat the
                 server writes as, so handing it to a viewer in a different seat
                 is handing over a command that fails; and rendering it dimmed
                 rather than omitted would still put `data-claim-command` on the
                 page, which `web/tests/unassigned.spec.js` reads as a control. -->
            <el-button v-if="claimable(t)" size="small" text type="primary" class="aim-claim"
                       :loading="claimBusy === t.id"
                       :aria-label="`Claim ${t.id} as ${board.writer}: ${claimCommand(t)}`"
                       :data-claim-command="claimCommand(t)" :data-claim-id="t.id"
                       :data-claim-as="board.writer" :data-claim-channel="t.channel || t.context_id || ''"
                       :title="`Takes it for ${board.writer} — runs ${claimCommand(t)}`"
                       @click.stop="applyClaim(t)">{{ claimCommand(t) }}</el-button>
            <span v-else class="aim-dim" style="font-size:11px"
                  title="A claim writes as one seat, and this board does not write as this viewer. A read can borrow a view; a write cannot borrow a name.">
              nobody on this seat can take it
            </span>
          </div>
          <!-- T-0161 clause 3: the acceptance is clamped rather than dropped, so
               the reader can still see *what* the card is and opens the drawer,
               which holds the whole item, for the rest of it. `compact` is now
               the reader's own "and not even that", one step inside the bound. -->
          <div v-if="t.accept" class="aim-accept aim-accept-clamp"
               :class="{ 'aim-accept-collapsed': compact }">
            <el-icon style="margin-top:2px"><Aim /></el-icon><span>{{ t.accept }}</span>
          </div>
          <div class="aim-meta">
            <OwnerAvatar :id="t.owner" :size="18" />
            <span v-if="t.due" :class="{ 'aim-late': isOverdue(t.due, t.status, board.terminal) }">
              {{ t.due.slice(5) }}{{ isOverdue(t.due, t.status, board.terminal) ? ' late' : '' }}
            </span>
            <span v-if="t.milestone">{{ t.milestone }}</span>
            <template v-for="b in t.blocked_by || []" :key="b">
              <!-- T-0203: the state is a word before it is a hue. The lock is the
                   decoration and says nothing on its own -- with author colours
                   replaced (the reason `card-t0203-a11y.spec.js` emulates forced
                   colours) an unnamed glyph is not a channel at all. -->
              <span class="aim-flag blocked" title="blocked by this work item">
                <el-icon aria-hidden="true"><Lock /></el-icon>blocked {{ b }}
              </span>
            </template>
            <span v-if="t.priority" class="aim-flag"
                  :style="{ color: t.priority === 'high' ? 'var(--aim-danger)' : 'inherit' }">
              <el-icon><Top v-if="t.priority === 'high'" /><Bottom v-else /></el-icon>{{ t.priority }}
            </span>
          </div>
          <!-- T-0188 clause 3: the promise mark is the shared component, not a
               chip this pane spells for itself. A per-pane rendering of one
               concept is the second answer the store's `isPromise` exists to
               prevent (`board.js:62`), and the card found the pane drawing
               `<span class="aim-chip seed">plan seed</span>` -- indistinguishable
               from a tag chip to a reader and invisible to a test that asks for
               `.aim-promise`. The wrapper's own condition reads the predicate
               too, so a card that draws the mark and a card the predicate calls a
               promise cannot be two different sets. -->
          <div v-if="(t.tags || []).length || t.visibility === 'draft' || isPromise(t)"
               style="display:flex;gap:5px;flex-wrap:wrap;margin-top:8px">
            <PromiseTag v-if="isPromise(t)" />
            <span v-if="t.visibility === 'draft'" class="aim-chip draft">draft</span>
            <span v-for="g in (t.tags || []).slice(0, 4)" :key="g" class="aim-chip">{{ g }}</span>
          </div>
        </article>
      </VueDraggable>
    </section>
  </div>

  <!-- The bound, stated: which page of the filtered cards is drawn, over the total
       the filters select. Without it a bound is a page that silently dropped work. -->
  <el-pagination v-model:current-page="page" :page-size="per" :total="matched"
                 :pager-count="7" layout="total, prev, pager, next, jumper"
                 background class="aim-pager" />
</template>

<style>
/* Scoped styles would not reach these: the classes are written on the card's own
   children and `style.css` is another task's file this round. The clamp is
   `-webkit-line-clamp` with an explicit `overflow: hidden`, because the line
   clamp on its own leaves the third line's leading visible on some engines.
   Three lines is the bound T-0161 clause 3 asks for: enough of an acceptance to
   recognize the card, short enough that the column stays a column of cards. */
.aim-accept.aim-accept-clamp span {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
}
/* The second step of the same bound: the reader asked for the title alone. */
.aim-accept.aim-accept-collapsed { display: none; }
.aim-pager { margin-top: 14px; justify-content: flex-end; }
/* Sits between the filter bar and the board, so a tag the picker collapsed into
   `+ 1` still has a control of its own. */
.aim-tagrow { display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
              margin: -4px 0 10px; font-size: 11px; color: var(--aim-dim); }
</style>
