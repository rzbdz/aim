<script setup>
import { computed, ref } from 'vue'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { listQuery } from '../composables/useTaskDrawer'
import PromiseTag from '../components/PromiseTag.vue'
import TaskLink from '../components/TaskLink.vue'
import { CALENDAR_ZONE } from '../dates'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  q: '', progress: 'all', owner: '', riskOwner: '',
})
const r = computed(() => board.register || {})
/**
 * The milestone figures are over the record, and the promise count is stated apart.
 *
 * `board.tasks` is the plan's seeds and the recorded items merged, so this row was
 * arithmetic about `plan/plan.json` presented as progress: measured live on
 * 2026-09-22, 124 items were counted, 87 of them seeds, and **43 of the 45 counted
 * "done" were seeds**. M7 rendered `100%` `2/2` with zero recorded items behind it.
 * A plan row's `status: done` is plan-authored text -- a seed has no events at all,
 * so nothing moved it.
 *
 * The progress bar is therefore `board.recorded`, the same authority the landing
 * page counts with (`OverviewPane.vue`), and the seed count rides beside it rather
 * than inside it: the reader is told both numbers and which is which, because a
 * number without its authority is the defect this whole card is about. Seeds are
 * promises -- work that has not been recorded -- and a promise is not progress.
 */
const milestones = computed(() => Object.values(board.milestones).map((m) => {
  const mine = board.tasks.filter((t) => t.milestone === m.id)
  const recorded = mine.filter((t) => !isPromise(t))
  const done = recorded.filter((t) => board.terminal.includes(t.status)).length
  return { ...m, done, total: recorded.length, promises: mine.length - recorded.length,
           pct: recorded.length ? Math.round(100 * done / recorded.length) : 0 }
}))
const searchable = (value) => String(value || '').toLowerCase()
const visibleMilestones = computed(() => milestones.value.filter((m) => {
  if (filters.q && !`${m.id} ${m.name} ${m.accept}`.toLowerCase().includes(filters.q.toLowerCase())) return false
  if (filters.progress === 'open' && m.pct >= 100) return false
  if (filters.progress === 'done' && m.pct < 100) return false
  if (filters.owner) {
    const all = board.tasks.filter((task) => task.milestone === m.id)
    if (!all.some((task) => task.owner === filters.owner)) return false
  }
  return true
}))
const visibleRisks = computed(() => (r.value.risks || []).filter((risk) => {
  if (filters.q && !`${risk.id} ${risk.risk} ${risk.mitigation} ${risk.kill_if}`.toLowerCase().includes(filters.q.toLowerCase())) return false
  if (filters.riskOwner && risk.owner !== filters.riskOwner) return false
  return true
}))
const visibleDecisions = computed(() => (r.value.decisions || []).filter((decision) => {
  if (!filters.q) return true
  return `${decision.id} ${decision.decision} ${decision.because}`.toLowerCase().includes(filters.q.toLowerCase())
}))
const visibleRaci = computed(() => (r.value.raci || []).filter((row) => {
  if (filters.q && !searchable(`${row.area} ${row.responsible} ${row.accountable} ${row.consulted}`).includes(filters.q.toLowerCase())) return false
  if (filters.owner && ![row.responsible, row.accountable, row.consulted].includes(filters.owner)) return false
  return true
}))
const riskOwners = computed(() => [...new Set((r.value.risks || []).map((risk) => risk.owner).filter(Boolean))].sort())
/**
 * Two halves of a due-date sentence that mean opposite things, measured apart.
 *
 * `66 item(s) have no due date, which in a plan is a sentence without a verb` was
 * rendered over `board.tasks` -- the merged board -- and the payload splits that
 * set as 0 plan seeds and all of them recorded items. So the clause collects its
 * noun ("in a plan") from one universe and its count from the other. Both halves
 * are stated because both are true of a different thing: an undated *seed* is a
 * promise the plan has not dated, an undated *recorded* item is one the reader has
 * not dated. Collapsing them into one number is how the first reading got applied
 * to the second set.
 */
const undated = computed(() => board.tasks.filter((task) => !task.due))
/** The half that belongs to the plan: promises carrying no date at all. */
const undatedPromises = computed(() => undated.value.filter((task) => isPromise(task)).length)

/**
 * The 87 rows, split by what the store actually holds. This split is the whole
 * fix, and it comes from the payload rather than from a second query.
 *
 * `aimboard/fold.py:126` emits two genuinely different rows under one name:
 * `store: None` when the store has *no record* of the id at all, and a differing
 * value when it has one. The old sentence claimed the second for all 87, so the
 * only resolution rule on the page was stated in the future tense of a comparison
 * that never happened for 100% of the count it carried. `!row.store` is the same
 * test the landing page already uses (OverviewPane.vue:358) and the right one:
 * `store: ""` is truthlessly absent too, and no status or date is falsy.
 *
 * A row whose store value is absent is not a row the store decided; it is a row
 * nothing has been recorded about yet. That is what the reader is told, and
 * `plan: null` (a record the plan does not mention) is rendered as "the plan says
 * nothing" rather than as an empty cell.
 */
const driftNeverRecorded = computed(() => board.drift.filter((row) => !row.store))
const driftDiffering = computed(() => board.drift.filter((row) => row.store))
/**
 * One slice, read by the rows, the "M more" tail and the header, so the three
 * cannot come out as three different numbers. The tail is `total - drawn` rather
 * than `total - budget`, so what it prints stays a property of what is on the
 * screen if the budget ever changes.
 */
const driftRowBudget = 20
const driftExpanded = ref(false)
const driftDrawn = computed(() => (driftExpanded.value
  ? driftNeverRecorded.value
  : driftNeverRecorded.value.slice(0, driftRowBudget)))
const driftRowsBelowBudget = computed(() =>
  Math.max(0, driftNeverRecorded.value.length - driftDrawn.value.length))
/**
 * The third kind of drift row, and the fact that an empty list is a finding.
 *
 * `drift()` emits `plan: null` for a recorded id the seed does not carry
 * (`aimboard/fold.py:249`), which is drift in the other direction: the board is
 * the seed and the record merged, so a record outside the plan means the plan no
 * longer describes the board. It is kept apart from the two lists above rather
 * than folded in, because what empties it is a plan edit and what empties those
 * is a recording.
 *
 * `drift_withheld` is read off the payload because the store hides rows a seat
 * may not see (`aimboard/api.py:77-85`): a list drawn over that slice is a slice,
 * and a reader who is not told the withheld count cannot tell a complete list
 * from a gated one (T-0210: "a drift list that can be emptied" has to be able to
 * say it is empty).
 */
const driftPlanMissing = computed(() => board.drift.filter((row) => row.plan == null))
const driftWithheld = computed(() => board.doc?.drift_withheld || 0)
const noDrift = computed(() => !driftNeverRecorded.value.length
  && !driftDiffering.value.length && !driftPlanMissing.value.length)

/**
 * The hours a milestone's rows declare, and the rule that keeps the figure
 * honest (T-0212).
 *
 * The sum reads `estimate_hours` and nothing else: the plan's `estimate` is in
 * points and is deliberately *not* converted here, because the migration is one
 * stated rule applied by a recorded script (`aimboard/fold.py`'s
 * `ESTIMATE_MIGRATION`) and a template that multiplied points by an hour would be
 * a second, silent copy of it. So a row that declares no hours is counted as
 * unknown and named, never as zero, and every figure leaves this map with its
 * unit already attached.
 */
const milestoneEstimate = computed(() => Object.fromEntries(milestones.value.map((m) => {
  const mine = board.tasks.filter((t) => t.milestone === m.id)
  const hours = mine.filter((t) => typeof t.estimate_hours === 'number')
  return [m.id, { rows: mine.length, estimated: hours.length,
                  hours: hours.reduce((sum, t) => sum + t.estimate_hours, 0) }]
})))

/**
 * The action a decision carries, rendered exactly as the payload states it
 * (T-0211).
 *
 * `design/12` §1.3: a control with no exact argv behind it is a dead end, and the
 * argv is the server's to publish -- a command rebuilt in a template drifts from
 * the verb the tool actually accepts, which is the lesson `aimboard/fold.py:164`
 * records for `claim`. So this pane draws the argv it is given and, where a
 * decision carries none, says so and draws no control: an action that cannot be
 * run is stated, not buttoned.
 */
const decisionActions = (decision) => decision.actions || []

const argvLine = (action) => {
  const argv = action.argv || []
  const parts = action.verb && argv[0] !== action.verb ? [action.verb, ...argv] : argv
  return `aim ${parts.join(' ')}`
}
</script>

<template>
  <el-alert type="info" :closable="false" show-icon style="margin-bottom:14px">
    <template #title>
      plan/*.json is the leader's plan and a <b>seed</b>. It is not a record, and being counted
      does not make it one: {{ driftNeverRecorded.length }} plan item(s) are in the plan and not
      in the store yet — the store's value for every one of them is
      <span class="aim-mono">not recorded</span>, because there is no record of them at all, so
      there is no store value for the store to win with. What resolves those rows is recording
      the item, which is an action rather than a verdict. A store value <i>is</i> evidence and a
      promise is not, so the rule still holds where it can apply:
      <template v-if="driftDiffering.length">both sides hold a value and differ on
        {{ driftDiffering.length }} field(s), the store wins, and that is the list under
        “Plan and store differ”.</template>
      <template v-else>no field here is one both sides hold and disagree on — measured over the
        plan and the store together, that count is 0 — so the store-wins rule has nothing to
        win today.</template>
      Both lists are drawn below, and the same two are on the
      <RouterLink :to="{ path: '/attention', hash: '#drift' }">attention page</RouterLink>.
      {{ driftPlanMissing.length }} recorded item(s) run the other way — in the store and not in
      the plan — and {{ noDrift ? 'the three lists together are empty: there is no drift'
        : 'the three lists below are every drift row this seat can see' }}{{ driftWithheld
        ? `, with ${driftWithheld} row(s) withheld from this seat` : '' }}. Of
      the {{ undated.length }} item(s) with no due date, {{ undatedPromises }} are plan promises
      waiting on a date and {{ undated.length - undatedPromises }} are recorded items with a date
      nobody set — both are sentences without a verb, but only the first is a hole in this plan.
    </template>
  </el-alert>

  <!-- The rows the two counts above are about, drawn where the counts are stated.
       The card asks for this: the sentence named 87 "disagreements" and the nearest
       row a reader could look at was a link into another pane (T-0183: a link that
       did not even scroll), so the number had nothing behind it here. Bounded at
       `driftRowBudget` with the remainder stated and expandable, rather than
       dumping 87 rows onto a plan page -- and the two kinds of row are drawn as two
       lists, because "the store has no value" and "the store has a different value"
       are different findings with different actions. -->
  <!-- Both columns are drawn on every drift row, and they are two provenances
       rather than two renderings of one value: "value in the plan" and "value in
       the store". A row where the store holds nothing is a row nothing has been
       recorded about -- the T-0190 defect was printing the store-wins rule over
       rows like that, where there was no store value for the store to win with.
       `not recorded` and `the plan says nothing` are the absences, and they are
       not the same absence. -->
  <el-card v-if="driftNeverRecorded.length" id="plan-drift" shadow="never" class="aim-drift-card"
           style="margin-bottom:14px">
    <template #header>
      <span>{{ driftNeverRecorded.length }} plan item(s) are not in the store yet</span>
      <!-- Not `?provenance=seed`: ItemsPane's filter set is q/owner/status/milestone/
           tag/onlyLate (ItemsPane.vue:11-13), so a provenance query would be a
           parameter no pane reads -- the link would land on the unfiltered list and
           promise a narrowing it did not do. The ids below open the drawer, which
           is the surface that actually offers "Record this work item". -->
      <RouterLink to="/items">the merged list, promises included</RouterLink>
    </template>
    <p class="aim-dim" style="font-size:12px;margin-top:0">
      <code class="aim-mono">value in the store = not recorded</code> for every row here: the plan
      names the item and the store has no record of it at all, so there is no store value that could
      win. That is a different finding from the list under “Plan and store differ”, where both sides
      hold a value. Recording one is the action that empties this list — the plan file is the seed,
      and the record is made in the item, not in the sentence.
    </p>
    <p class="aim-dim" style="font-size:11px;margin:0 0 4px">
      each row reads: id · field · <b>value in the plan</b> · <b>value in the store</b>
    </p>
    <article v-for="row in driftDrawn" :key="`${row.id}-${row.field}`" class="aim-attention-row">
      <TaskLink :id="row.id" />
      <strong>{{ row.field }}</strong>
      <span>{{ row.plan ?? 'the plan says nothing' }}</span>
      <!-- The store's own word for this row is the predicate, and the row says
           which half it is about: rendered with the cell alone, this row read as
           a value a reader could compare (T-0190's defect one scope down), and
           `store has not recorded` is not a sentence about anything. The words
           `store has` are the landing page's drift row (`OverviewPane.vue:767`),
           so the same fact is one phrase on both pages rather than two. -->
      <span>the store has no record of this item:
        <code class="aim-mono">not recorded</code>
        <PromiseTag title="Nothing recorded: this row is a plan promise the store has never seen." /></span>
    </article>
    <p v-if="driftRowsBelowBudget || driftExpanded" class="aim-dim"
       style="font-size:12px;margin-bottom:0">
      <!-- The remainder is stated as a number rather than as "and more", because a
           reader who is told 67 rows are hidden can decide whether to expand; a
           reader told "more" cannot. The control expands in place, so the count,
           the rows and the tail are still one card and not a link into another
           pane (T-0183 measured that link not scrolling at all). -->
      <button type="button" class="aim-task-link" @click="driftExpanded = !driftExpanded">
        {{ driftExpanded ? 'show only the first ' + driftRowBudget
                         : 'show all ' + driftNeverRecorded.length + ' (' + driftRowsBelowBudget + ' more)' }}
      </button>
    </p>
  </el-card>

  <el-card v-if="driftDiffering.length" id="plan-drift-differs" shadow="never" class="aim-drift-card"
           style="margin-bottom:14px">
    <template #header><span>Plan and store differ on {{ driftDiffering.length }} field(s)</span></template>
    <p class="aim-dim" style="font-size:12px;margin-top:0">
      Both sides hold a value here and they are not the same value — this is the only list the
      store-wins rule is about. The store wins: one of these is what happened, and the plan column
      is what the plan still promises.
    </p>
    <p class="aim-dim" style="font-size:11px;margin:0 0 4px">
      each row reads: id · field · <b>value in the plan</b> · <b>value in the store</b>
    </p>
    <article v-for="row in driftDiffering" :key="`${row.id}-${row.field}`" class="aim-attention-row">
      <TaskLink :id="row.id" />
      <strong>{{ row.field }}</strong>
      <span>{{ row.plan ?? 'the plan says nothing' }}</span>
      <span><b>{{ row.store }}</b></span>
    </article>
  </el-card>

  <el-card v-if="driftPlanMissing.length" id="plan-drift-unplanned" shadow="never" class="aim-drift-card"
           style="margin-bottom:14px">
    <template #header><span>{{ driftPlanMissing.length }} recorded item(s) the plan does not name</span></template>
    <p class="aim-dim" style="font-size:12px;margin-top:0">
      The reverse direction: the store holds the row and <code class="aim-mono">plan = not named</code>.
      These do not empty by recording — they empty by the plan naming them, which is an edit to the
      seed.
    </p>
    <p class="aim-dim" style="font-size:11px;margin:0 0 4px">
      each row reads: id · field · <b>value in the plan</b> · <b>value in the store</b>
    </p>
    <article v-for="row in driftPlanMissing" :key="`${row.id}-${row.field}`" class="aim-attention-row">
      <TaskLink :id="row.id" />
      <strong>{{ row.field }}</strong>
      <span class="aim-dim">the plan says nothing</span>
      <span>{{ row.store ?? 'not recorded' }}</span>
    </article>
  </el-card>

  <!-- An empty drift list is a finding about the two sources, so it is stated
       rather than left as an absent card: three lists that render nothing look
       exactly like three lists that were never computed. A gated list is not an
       empty one either, so the withheld count is published beside the verdict. -->
  <el-alert v-if="noDrift" type="success" :closable="false" show-icon
            id="plan-drift-empty" style="margin-bottom:14px">
    <template #title>
      no drift: every plan item the store has recorded agrees with the plan field by field
      ({{ driftWithheld ? driftWithheld + ' row(s) withheld from this seat, so this is the ' +
        'visible slice and not the whole store' : 'no row withheld, so this is the whole store' }}).
    </template>
  </el-alert>
  <p v-else-if="driftWithheld" class="aim-dim" style="font-size:12px">
    {{ driftWithheld }} drift row(s) withheld from this seat: the lists above are what this seat may
    see, not the whole store.
  </p>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>milestones ({{ visibleMilestones.length }} of {{ milestones.length }}) — progress counts
          <b>the record</b>, the <code class="aim-mono">planned</code> chips are plan seeds</span>
        <!-- Every `due` below is a bare `YYYY-MM-DD`: it carries no instant, so
             there is nothing to convert and nothing to append to the cell. What it
             does have is a calendar it is read in -- `plan/plan.json:5`, which
             `design/17-org-and-project.md` §4 names as the source ("a task due
             'today' is due in the leader's day and not in UTC's") and `dates.js`
             `CALENDAR_ZONE` reads. Said once here, over the column, rather than
             repeated in every row. -->
        <span class="aim-dim" style="font-size:11.5px">every due date is a calendar day
          in {{ CALENDAR_ZONE }}</span>
        <el-input v-model="filters.q" placeholder="search milestones, risks, decisions"
                  aria-label="search milestones, risks and decisions" clearable />
        <el-select v-model="filters.progress" placeholder="progress" aria-label="filter milestones by progress">
          <el-option value="all" label="all progress" />
          <el-option value="open" label="open" />
          <el-option value="done" label="done" />
        </el-select>
        <el-select v-model="filters.owner" placeholder="work owner" aria-label="filter milestones by work owner" clearable>
          <el-option v-for="owner in board.owners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-select v-model="filters.riskOwner" placeholder="risk owner" aria-label="filter risks by owner" clearable>
          <el-option v-for="owner in riskOwners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
      </div>
    </template>
    <el-table :data="visibleMilestones" size="small">
      <el-table-column label="id" width="86">
        <template #default="{ row }">
          <!-- A milestone is a way into the work it is made of, rather than a
               label the reader has to go and search for. -->
          <RouterLink :to="{ path: '/items', query: listQuery('milestone', row.id) }"
                      class="aim-task-link">{{ row.id }}</RouterLink>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="name" min-width="200" />
      <el-table-column prop="due" label="due" width="110" />
      <el-table-column label="progress — recorded items" width="270">
        <template #default="{ row }">
          <!-- The bar and the fraction are one number and it is the record's:
               `M7 100% 2/2` over zero recorded items was the card's own example of
               the failure. The denominator is stated here so the reader does not
               have to guess which half of the board it came from. -->
          <el-progress :percentage="row.pct" :stroke-width="10" />
          <span class="aim-dim" style="font-size:11px">{{ row.done }}/{{ row.total }} recorded</span>
          <span v-if="row.promises" class="aim-dim" style="font-size:11px"> ·
            <span class="aim-chip seed">{{ row.promises }} planned</span></span>
        </template>
      </el-table-column>
      <!-- The unit rides on the number and a row with no estimate is "not
           estimated", never 0 h: the plan's `estimate` is in points and is not
           converted here, because that conversion is one stated rule applied by a
           recorded script (`ESTIMATE_MIGRATION`), not arithmetic in a template
           (T-0212). -->
      <el-table-column label="estimate — declared hours" width="210">
        <template #default="{ row }">
          <template v-if="milestoneEstimate[row.id]?.estimated">
            {{ milestoneEstimate[row.id].hours }} h over
            {{ milestoneEstimate[row.id].estimated }} of {{ milestoneEstimate[row.id].rows }} row(s)
          </template>
          <span v-else class="aim-dim">not estimated ({{ milestoneEstimate[row.id]?.rows || 0 }} row(s))</span>
        </template>
      </el-table-column>
      <el-table-column prop="accept" label="acceptance — the sentence that makes it verifiable" min-width="380" />
    </el-table>
  </el-card>

  <div class="aim-grid">
    <el-card shadow="never">
      <template #header>risks ({{ visibleRisks.length }})</template>
      <el-table :data="visibleRisks" size="small">
        <el-table-column prop="id" label="id" width="66" />
        <el-table-column prop="risk" label="risk" min-width="300" />
        <el-table-column prop="likelihood" label="likelihood" width="100" />
        <el-table-column prop="impact" label="impact" width="90" />
        <el-table-column prop="owner" label="owner" width="110" />
        <el-table-column prop="mitigation" label="mitigation" min-width="320" />
        <el-table-column prop="kill_if" label="what would close it" min-width="260" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>decisions ({{ visibleDecisions.length }})</template>
      <el-collapse>
        <el-collapse-item v-for="d in visibleDecisions" :key="d.id" :name="d.id">
          <template #title><b style="margin-right:8px">{{ d.id }}</b> {{ d.decision }}</template>
          <p class="aim-dim">because {{ d.because }}</p>
          <!-- T-0211: the control and its argv are one object, and the argv is the
               server's to publish — a verb rebuilt in a template is a second copy of
               the verb (`aimboard/fold.py:164`). A decision carrying none is stated
               as carrying none rather than given a button with nothing behind it. -->
          <ul v-if="decisionActions(d).length" style="list-style:none;padding:0;margin:6px 0 0">
            <li v-for="(a, i) in decisionActions(d)" :key="i" style="margin-bottom:6px">
              <strong>{{ a.label || a.key }}</strong>
              <code class="aim-mono" style="display:block;word-break:break-word">{{ argvLine(a) }}</code>
              <span v-if="a.detail" class="aim-dim" style="font-size:11.5px">{{ a.detail }}</span>
            </li>
          </ul>
          <p v-else class="aim-dim" style="font-size:11.5px">
            no actions[] with a runnable argv — nothing here is approximated as a control.
          </p>
        </el-collapse-item>
      </el-collapse>
      <h4>non-goals</h4>
      <ul style="padding-left:18px;font-size:12.5px">
        <li v-for="(n, i) in r.non_goals || []" :key="i">{{ n }}</li>
      </ul>
    </el-card>
  </div>

  <el-card shadow="never" style="margin-top:14px">
    <template #header>who does what ({{ visibleRaci.length }})</template>
    <el-table :data="visibleRaci" size="small">
      <el-table-column prop="area" label="area" min-width="240" />
      <el-table-column prop="responsible" label="responsible" width="170" />
      <el-table-column prop="accountable" label="accountable" width="150" />
      <el-table-column prop="consulted" label="consulted" width="170" />
    </el-table>
    <template v-if="r.dogfooding">
      <h4>dogfooding — {{ r.dogfooding.rule }}</h4>
      <ul style="padding-left:18px;font-size:12.5px">
        <li v-for="(p, i) in r.dogfooding.practices || []" :key="i">{{ p }}</li>
      </ul>
      <p class="aim-dim" style="font-size:12px">kill_if: {{ r.dogfooding.kill_if }}</p>
    </template>
  </el-card>
</template>
