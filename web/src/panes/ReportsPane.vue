<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { listQuery } from '../composables/useTaskDrawer'
import { STATUS_TYPE, statusLabel } from '../theme'
import TaskLink from '../components/TaskLink.vue'

const board = useBoard()
/**
 * The window is minutes, not hours.
 *
 * The question this page answers is "is anything happening right now", and a
 * day is not a unit you can answer that in: the fabric recorded 85 cards closed
 * in one afternoon, and at day resolution that afternoon is a single point on
 * the x-axis with nothing to see inside it. `window` is therefore minutes, the
 * buckets are one minute wide, and the select offers 15 minutes through a day.
 *
 * `per` and the blocked-table filters were already here and still deep-link.
 */
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', blocker: '', window: '60', per: '25',
})

const option = computed(() => {
  const r = board.report
  const dates = (r.series || []).map((x) => x.date.slice(5))
  return {
    backgroundColor: 'transparent',
    grid: { left: 52, right: 24, top: 24, bottom: 34 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['remaining', 'done'], top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1, name: 'items', nameTextStyle: { fontSize: 10 },
             splitLine: { lineStyle: { opacity: 0.18 } } },
    series: [
      { name: 'remaining', type: 'line', smooth: true, data: (r.series || []).map((x) => x.remaining), areaStyle: { opacity: 0.12 } },
      { name: 'done', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, data: (r.series || []).map((x) => x.done) },
    ],
  }
})
const burndownEmpty = computed(() => !(board.report.series || []).some((x) => x.done || x.remaining))

/* ---------------------------------------------------------------------------
 * Flow by the minute (T-0217).
 *
 * The fold emits a per-day `series` and nothing finer, so these buckets are
 * derived here from the event timestamps the payload already ships on every
 * task. Nothing is invented: a bucket counts a recorded `created` or a recorded
 * `moved -> done`, and a plan seed has no events, so a seed cannot be counted as
 * work that started.
 *
 * Minute resolution is the point of the rewrite, not a detail of it. A reader
 * watching this board work wants to see the line move between two refreshes,
 * and one-minute buckets are what makes a close visible as it happens rather
 * than as part of an afternoon.
 * ------------------------------------------------------------------------- */

const BUCKET_MS = 60000
/** Minutes. 15m is one screenful of buckets; 1440 is the whole day so far. */
const WINDOWS = [15, 30, 60, 180, 360, 720, 1440]
const DEFAULT_WINDOW = 60
const PAGE_SIZES = [25, 50, 100]

/** Newest arrivals listed under the chart; the reader is watching these. */
const ARRIVALS = 14

/**
 * Non-colour status marks.
 *
 * `STATUS_TYPE` is a colour, and a reader who cannot see it has no status at
 * all; the glyph rides beside the word so the row reads the same with colour
 * ignored, and the drawer keeps the same vocabulary.
 */
const STATUS_GLYPH = {
  backlog: '·', ready: '○', doing: '◐', review: '◆', done: '✔', blocked: '✖', dropped: '–',
}

const windowMinutes = computed(() => (WINDOWS.includes(Number(filters.window))
  ? Number(filters.window)
  : DEFAULT_WINDOW))

/** Every recorded open and close, as one list, because the chart is one timeline. */
const events = computed(() => {
  const out = []
  for (const task of board.tasks) {
    for (const ev of task.events || []) {
      if (!ev.ts) continue
      const kind = String(ev.event || ev.kind || '').replace(/^task\./, '')
      if (kind === 'created') out.push({ ts: Date.parse(ev.ts), kind: 'opened', id: task.id, title: task.title, actor: ev.actor })
      else if (kind === 'moved' && ev.to === 'done') out.push({ ts: Date.parse(ev.ts), kind: 'done', id: task.id, title: task.title, actor: ev.actor })
    }
  }
  return out.filter((e) => Number.isFinite(e.ts)).sort((a, b) => a.ts - b.ts)
})

/**
 * The minute a moment belongs to, as a number.
 *
 * Every timestamp on this page is floored to a minute boundary and rendered
 * from that, so two events fifty seconds apart carry the same tag and the
 * reader can tell "these arrived in the same minute" from "these arrived a
 * minute apart". Rounding at render time instead would put two rows in one
 * bucket and label them with different clock times, which is the kind of
 * off-by-one-minute that makes a tally not add up.
 */
const minuteOf = (ms) => Math.floor(ms / BUCKET_MS) * BUCKET_MS
const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const stamp = (ms) => `${clock(minuteOf(ms))}`

/**
 * When this pane started looking.
 *
 * An arrival after this moment is one the reader could not have seen on the
 * last refresh, and marking it is the difference between a chart that is live
 * and a chart that merely updates. It is a `Date.now()` floor and not a server
 * timestamp on purpose: the question is what *this reader* has already seen.
 */
const watchingSince = ref(Date.now())
const boardRefreshes = ref(0)
watch(events, () => { boardRefreshes.value += 1 })

/**
 * How the whole board stands right now: done, dropped, and still undone.
 *
 * This is not derivable from the events above, and that is the point of it being
 * a separate tally. `events` counts *moves*, so a task done before the window
 * opened contributes no event and would be invisible to a figure built from
 * them -- which is exactly the reading the leader was missing: a chart of
 * closes per minute with no line for the work still standing reads as though
 * every minute of it were progress toward nothing.
 *
 * Terminal means the two statuses that are not outstanding work. `blocked` is
 * deliberately not one of them: a blocked item is unfinished, and counting it
 * as finished is the failure this line exists to make visible.
 */
const tally = computed(() => {
  const out = { undone: 0, done: 0, dropped: 0, total: 0 }
  for (const t of board.tasks) {
    out.total += 1
    const s = t.status
    if (s === 'done') out.done += 1
    else if (s === 'dropped') out.dropped += 1
    else out.undone += 1
  }
  return out
})

/** How much of the board is finished, as a percentage of the work that can be. */
const finishedPct = computed(() => {
  const t = tally.value
  const denominator = t.done + t.undone
  return denominator ? Math.round((t.done / denominator) * 100) : 0
})

const flow = computed(() => {
  // The window ends at the newest recorded event, not at the clock: a store
  // whose last write was an hour ago would otherwise open on a screen of empty
  // minutes and read as a quiet fabric rather than as a stale one. `live` says
  // which of the two the reader is looking at.
  const end = events.value.length ? events.value.at(-1).ts : Date.now()
  const endBucket = minuteOf(end) + BUCKET_MS
  const start = endBucket - windowMinutes.value * BUCKET_MS
  const cells = Array.from({ length: windowMinutes.value }, (_, i) => ({
    t: start + i * BUCKET_MS, opened: 0, done: 0,
  }))
  for (const e of events.value) {
    if (e.ts < start || e.ts >= endBucket) continue
    cells[Math.floor((e.ts - start) / BUCKET_MS)][e.kind] += 1
  }
  const opened = cells.reduce((n, c) => n + c.opened, 0)
  const done = cells.reduce((n, c) => n + c.done, 0)

  // Running total of closes, so "progressively" is a shape on the chart and not
  // only a number: the reader wants to see the line climb, and a per-minute bar
  // alone shows rate without showing how far along the work is.
  let running = 0
  const cumulative = cells.map((c) => (running += c.done))

  // The same running total for opens, because one cumulative line says what was
  // finished and nothing says what was started. Two lines on one axis is the
  // whole reading: the gap between them is work this window created and did not
  // close, and a window where the blue line is above the green one is a board
  // going backwards however busy the bars look. This is *not* the count of
  // undone work -- a task that existed before the window opened has no event
  // here at all -- and `tally` below is the honest figure for that. Naming the
  // difference is why both exist.
  let opening = 0
  const openedCumulative = cells.map((c) => (opening += c.opened))

  // The longest run of minutes with nothing recorded. At minute resolution this
  // is the signal that matters most -- a fabric that has been quiet for eleven
  // minutes is stalling, and no per-minute bar chart says that on its own.
  let run = 0
  let best = null
  cells.forEach((c, i) => {
    if (c.opened || c.done) { run = 0; return }
    run += 1
    if (!best || run > best.count) best = { count: run, end: i + 1 }
  })
  const gap = best ? { from: cells[best.end - best.count].t, to: cells[best.end - 1].t + BUCKET_MS,
                       minutes: best.count } : null

  // A burst is many opens inside one minute against what the window usually
  // shows, which is how a scripted import is told apart from work starting.
  const opens = cells.map((c) => c.opened).filter(Boolean).sort((a, b) => a - b)
  const median = opens.length ? opens[opens.length >> 1] : 0
  const burst = cells.filter((c) => c.opened >= Math.max(4, median * 3)).sort((a, b) => b.opened - a.opened)[0] || null

  const lastEvent = events.value.at(-1)
  const quietMinutes = lastEvent ? (Date.now() - lastEvent.ts) / BUCKET_MS : null
  return { cells, cumulative, openedCumulative, start, end: endBucket, opened, done, gap, burst, lastEvent, quietMinutes }
})

/**
 * The newest arrivals, one row per event, newest first.
 *
 * This is the list the reader actually watches: every close carries the minute
 * it landed in, so a card done at 17:41 and a card done at 17:43 are two rows
 * with two minute tags rather than one afternoon total. The id is a `TaskLink`,
 * so a row that moved is one click from the card that moved.
 */
const arrivals = computed(() => [...events.value].reverse().slice(0, ARRIVALS).map((e) => ({
  ...e,
  minute: minuteOf(e.ts),
  fresh: e.ts >= watchingSince.value,
})))

const arrivalsSummary = computed(() => {
  const fresh = arrivals.value.filter((a) => a.fresh)
  if (!fresh.length) return ''
  const done = fresh.filter((a) => a.kind === 'done').length
  const opened = fresh.length - done
  return `${fresh.length} new arrival(s) since this page loaded: ${done} done, ${opened} opened.`
})

const flowOption = computed(() => {
  const f = flow.value
  const labels = f.cells.map((c) => clock(c.t))
  const every = Math.max(0, Math.ceil(f.cells.length / 12) - 1)
  return {
    backgroundColor: 'transparent',
    grid: { left: 52, right: 48, top: 30, bottom: 34 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['opened', 'done', 'opened cumulative', 'done cumulative'], top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, interval: every } },
    // The axis carries its unit: a count of items over a minute bucket, and a
    // figure whose unit is only in the title is a figure somebody reads wrong.
    yAxis: [
      { type: 'value', minInterval: 1, name: 'items / min', nameTextStyle: { fontSize: 10 },
        splitLine: { lineStyle: { opacity: 0.18 } } },
      { type: 'value', minInterval: 1, name: 'running total', nameTextStyle: { fontSize: 10 },
        splitLine: { show: false } },
    ],
    // Different mark shapes as well as different colours: the series have to be
    // told apart by a reader who is not being shown the legend's colours.
    series: [
      { name: 'opened', type: 'bar', stack: 'permin', symbol: 'circle', symbolSize: 6,
        itemStyle: { color: '#60a5fa' }, barMaxWidth: 10, data: f.cells.map((c) => c.opened) },
      { name: 'done', type: 'bar', stack: 'permin', symbol: 'rect', symbolSize: 6,
        itemStyle: { color: '#34d399' }, barMaxWidth: 10, data: f.cells.map((c) => c.done) },
      // The two running totals on one axis are the whole reading: where the blue
      // line sits above the green one, the window created more than it closed.
      { name: 'opened cumulative', type: 'line', yAxisIndex: 1, step: 'end', symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5, type: 'dotted' }, data: f.openedCumulative },
      { name: 'done cumulative', type: 'line', yAxisIndex: 1, step: 'end', symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 2 }, data: f.cumulative,
        // What is *still* undone is not a trajectory, so it is drawn as a
        // reference line and not as a fifth series: a series would invite the
        // reader to watch it move, and it does not move with the window -- it is
        // the board's standing figure, taken over every task that exists.
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: '#f87171', type: 'dashed', width: 1.5 },
          label: { formatter: `undone ${tally.undone}`, fontSize: 10, position: 'insideEndTop' },
          data: [{ yAxis: tally.undone }],
        } },
    ],
  }
})

const flowSummary = computed(() => {
  const f = flow.value
  if (!f.opened && !f.done) return ''
  const parts = [`${f.opened} opened and ${f.done} done in the last ${windowMinutes.value} min, one bucket per minute`]
  if (f.gap) parts.push(`longest quiet run ${f.gap.minutes} min (${clock(f.gap.from)}–${clock(f.gap.to)})`)
  if (f.burst) parts.push(`busiest minute ${clock(f.burst.t)}: ${f.burst.opened} opened`)
  if (f.quietMinutes !== null && f.quietMinutes >= 2) {
    parts.push(`nothing recorded for ${Math.floor(f.quietMinutes)} min (last event ${clock(f.lastEvent.ts)})`)
  }
  return parts.join('; ')
})

/* ---------------------------------------------------------------------------
 * The blocked table, bounded (T-0161).
 * ------------------------------------------------------------------------- */

const blockedRows = computed(() => (board.report.blocked || []).filter((row) => {
  if (filters.q) {
    const needle = filters.q.toLowerCase()
    if (!`${row.id} ${row.title} ${(row.blocked_by || []).join(' ')}`.toLowerCase().includes(needle)) return false
  }
  if (filters.owner && row.owner !== filters.owner) return false
  if (filters.status && row.status !== filters.status) return false
  if (filters.blocker && !(row.blocked_by || []).includes(filters.blocker)) return false
  return true
}))
const blockerOptions = computed(() => [...new Set((board.report.blocked || [])
  .flatMap((row) => row.blocked_by || []))].sort())

/** Derived from the options, never taken on trust: `?per=99999` would unbind it. */
const perPage = computed(() => (PAGE_SIZES.includes(Number(filters.per)) ? Number(filters.per) : PAGE_SIZES[0]))
const page = ref(0)
const drawn = computed(() => blockedRows.value.slice(page.value * perPage.value, (page.value + 1) * perPage.value))

/** A filter change starts the reader at the top of the result, not mid-list. */
watch(() => [filters.q, filters.owner, filters.status, filters.blocker], () => { page.value = 0 })
watch([blockedRows, perPage], () => {
  const last = Math.max(0, Math.ceil(blockedRows.value.length / perPage.value) - 1)
  if (page.value > last) page.value = last
})

/** Milestones with work behind them, so the signal leads to the items it counts. */
const milestoneRows = computed(() => Object.entries(board.report.milestones || {})
  .map(([id, m]) => ({ id, ...m }))
  .sort((a, b) => (a.id < b.id ? -1 : 1)))

/**
 * A clock the page re-reads once a minute.
 *
 * The board already polls the record every 2.5s (`main.js`), so a new event
 * arrives on its own; what does not move without help is *time* -- the age of
 * the last event, and whether an arrival is still "new". A minute tick is the
 * interval the page is measuring in, so it is the interval it re-reads at.
 */
const now = ref(Date.now())
const tick = setInterval(() => { now.value = Date.now() }, 30000)
onUnmounted(() => clearInterval(tick))
const quietLabel = computed(() => {
  const last = flow.value.lastEvent
  if (!last) return 'no recorded event in this store'
  const mins = Math.floor((now.value - last.ts) / BUCKET_MS)
  if (mins <= 0) return `last event in this minute (${clock(last.ts)})`
  return `last event ${mins} min ago (${clock(last.ts)})`
})
</script>

<template>
  <div class="aim-grid" style="margin-bottom:14px">
    <el-card shadow="never">
      <!-- Every signal here is a way into the list it counts; when there is
           nothing to count it is words and not a link, because a link to an
           empty list reads as work that is not there. -->
      <el-statistic title="median cycle time (days)" :value="board.report.median_cycle ?? 0" />
      <RouterLink v-if="board.report.with_history" :to="{ path: '/items', query: listQuery('status', 'done') }"
                  class="aim-task-link" style="font-size:11.5px">
        {{ board.report.with_history }} item(s) with move history
      </RouterLink>
      <span v-else class="aim-dim" style="font-size:11.5px" data-zero="1">0 item(s) with move history</span>
    </el-card>
    <el-card shadow="never">
      <el-statistic title="recorded in the store (items)" :value="board.report.recorded" />
      <span class="aim-dim" style="font-size:11.5px">{{ board.report.seed_only }} item(s) are plan seed only</span>
    </el-card>
    <el-card shadow="never">
      <el-statistic title="closes in the drawn window (items)"
                    :value="(board.report.series || []).reduce((n, x) => n + (x.done || 0), 0)" />
      <span class="aim-dim" style="font-size:11.5px">over {{ (board.report.series || []).length }} recorded day(s)</span>
    </el-card>
  </div>

  <!-- The numbers above and below are folded over the whole fabric, not over this
       seat's board: a total that changed with who read it was reported as the
       project's figure by a consumer that could not tell, so the scope is stated
       on the page the same way the payload states it. -->
  <p class="aim-dim" style="font-size:12px; margin:0 0 14px">
    These counts describe the whole fabric, not this seat's view. The board's cards are gated:
    {{ board.withheld }} item(s) are withheld from the current view.
  </p>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>flow — opened vs done, one bucket per minute over the last {{ windowMinutes }} min
          ({{ flow.start ? `${clock(flow.start)}–${clock(flow.end)}` : 'no events' }})</span>
        <el-select v-model="filters.window" size="small" placeholder="window" data-filter="window">
          <el-option v-for="mins in WINDOWS" :key="mins" :value="String(mins)"
                     :label="mins < 60 ? `last ${mins} min` : `last ${mins / 60} h`" />
        </el-select>
      </div>
    </template>

    <el-alert v-if="!flow.opened && !flow.done" type="info" :closable="false" show-icon style="margin-bottom:10px"
              title="nothing recorded in this window: these buckets count recorded `created` and `moved -> done` events, and a plan seed has none" />

    <div class="aim-flow-stats">
      <span><strong>{{ tally.undone }}</strong> undone</span>
      <span><strong>{{ tally.done }}</strong> done</span>
      <span><strong>{{ tally.dropped }}</strong> dropped</span>
      <span><strong>{{ finishedPct }}%</strong> of the board finished</span>
      <span class="aim-dim"><strong>{{ tally.total }}</strong> work item(s) in this view</span>
      <span><strong>{{ flow.opened }}</strong> opened (items)</span>
      <span><strong>{{ flow.done }}</strong> done (items)</span>
      <span><strong>{{ (flow.opened / windowMinutes * 60).toFixed(1) }}</strong> opened / h</span>
      <span><strong>{{ (flow.done / windowMinutes * 60).toFixed(1) }}</strong> done / h</span>
      <span :class="flow.gap ? '' : 'aim-dim'">
        longest quiet run:
        <strong v-if="flow.gap">{{ flow.gap.minutes }} min</strong>
        <span v-else>none — every minute in this window has an event</span>
        <template v-if="flow.gap"> ({{ clock(flow.gap.from) }}–{{ clock(flow.gap.to) }})</template>
      </span>
      <span v-if="flow.burst">import burst: {{ flow.burst.opened }} opened in one minute at {{ clock(flow.burst.t) }}</span>
      <!-- The live signal: an event that landed inside the current minute is the
           one a reader watching this page is looking for. -->
      <span :class="flow.quietMinutes !== null && flow.quietMinutes < 2 ? 'aim-live' : 'aim-dim'">
        <span aria-hidden="true">●</span> {{ quietLabel }}
      </span>
      <span class="aim-dim">board refreshed {{ boardRefreshes }}× since this page loaded</span>
    </div>

    <!-- The chart carries the numbers as text too, so the series are readable
         when colour is not: the two marks differ in shape, and the summary below
         states the totals in items and minutes. -->
    <VChart :option="flowOption" autoresize aria-hidden="true" style="height:300px" />
    <p v-if="flowSummary" class="aim-dim" style="font-size:12px; margin:6px 0 0">{{ flowSummary }}</p>
  </el-card>

  <!-- The list the reader actually watches. Each row carries the minute its
       event landed in, so progress is legible one close at a time rather than
       only as a total that changed between two page loads. -->
  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>arrivals — newest {{ Math.min(ARRIVALS, events.length) }} recorded event(s), tagged by the minute</span>
        <RouterLink to="/items" class="aim-task-link" style="font-size:12px">all items →</RouterLink>
      </div>
    </template>
    <p v-if="arrivalsSummary" class="aim-live" style="font-size:12px; margin:0 0 8px">{{ arrivalsSummary }}</p>
    <el-table :data="arrivals" size="small" :row-class-name="({ row }) => (row.fresh ? 'aim-row-fresh' : '')">
      <el-table-column label="minute" width="76">
        <template #default="{ row }"><span class="aim-minute">{{ stamp(row.ts) }}</span></template>
      </el-table-column>
      <el-table-column label="what" width="92">
        <template #default="{ row }">
          <span :class="row.kind === 'done' ? 'aim-kind-done' : 'aim-kind-opened'">
            <span aria-hidden="true">{{ row.kind === 'done' ? '✔' : '＋' }}</span> {{ row.kind }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="item" width="120">
        <template #default="{ row }"><TaskLink :id="row.id" /></template>
      </el-table-column>
      <el-table-column prop="title" label="title" min-width="280" show-overflow-tooltip />
      <el-table-column label="by" width="150">
        <template #default="{ row }"><span class="aim-dim">{{ row.actor || '—' }}</span></template>
      </el-table-column>
    </el-table>
    <p class="aim-dim" style="font-size:12px; margin:8px 0 0">
      Only recorded work moves this page: a plan promise has no events, so it can never be
      counted here as something that started or finished. A row tinted
      <span class="aim-live">new</span> arrived after this page loaded.
    </p>
  </el-card>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>burndown — remaining work per day, folded from the whole store</template>
    <el-alert v-if="burndownEmpty" type="info" :closable="false" show-icon style="margin-bottom:10px"
              title="flat at zero because nothing is recorded in the store yet: this chart is drawn from events, and a plan seed has none" />
    <VChart :option="option" autoresize aria-hidden="true" style="height:320px" />
    <p class="aim-dim" style="font-size:12px; margin:6px 0 0">
      {{ (board.report.with_history || 0) }} item(s) closed by a recorded move, over {{ (board.report.series || []).length }} day(s).
    </p>
  </el-card>

  <!-- A milestone is a promise with a date, so the count leads to the items that
       carry it rather than sitting as a number the reader cannot act on. -->
  <el-card v-if="milestoneRows.length" shadow="never" style="margin-bottom:14px">
    <template #header>milestones — progress, and the items behind it</template>
    <div class="aim-flow-stats">
      <span v-for="m in milestoneRows" :key="m.id">
        <RouterLink v-if="m.total" :to="{ path: '/items', query: listQuery('milestone', m.id) }" class="aim-task-link">
          {{ m.name || m.id }} — {{ m.done }} of {{ m.total }} item(s) done
        </RouterLink>
        <span v-else class="aim-dim" data-zero="1">{{ m.name || m.id }} — 0 item(s)</span>
        <span class="aim-dim" style="font-size:11px">{{ m.due ? `due ${m.due}` : 'no due date' }}</span>
      </span>
    </div>
  </el-card>

  <el-card shadow="never">
    <template #header>
      <div class="aim-filterbar">
        <span>what is waiting on what — {{ blockedRows.length }} of {{ (board.report.blocked || []).length }} blocker row(s){{ board.report.blocked_withheld ? ` (${board.report.blocked_withheld} withheld from this view)` : '' }}</span>
        <el-input v-model="filters.q" placeholder="search blocked item" clearable />
        <el-select v-model="filters.owner" placeholder="owner" clearable>
          <el-option v-for="owner in board.owners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-select v-model="filters.status" placeholder="status" clearable>
          <el-option v-for="status in board.statuses" :key="status" :value="status" :label="statusLabel(status)" />
        </el-select>
        <el-select v-model="filters.blocker" placeholder="waiting on" clearable>
          <el-option v-for="blocker in blockerOptions" :key="blocker" :value="blocker" :label="blocker" />
        </el-select>
        <el-select v-model="filters.per" size="small" placeholder="per page" data-filter="per">
          <el-option v-for="size in PAGE_SIZES" :key="size" :value="String(size)" :label="`${size} / page`" />
        </el-select>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
      </div>
    </template>
    <el-table :data="drawn" size="small" max-height="66vh">
      <el-table-column label="blocked item" width="130">
        <template #default="{ row }"><TaskLink :id="row.id" /></template>
      </el-table-column>
      <el-table-column prop="title" label="title" min-width="300" />
      <el-table-column label="status" width="140">
        <!-- Colour is the tag type; the glyph and the word are what carry the
             status when colour is ignored (T-0203). -->
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TYPE[row.status] || 'info'" effect="plain"
                  :aria-label="`status: ${row.status}`">
            <span aria-hidden="true">{{ STATUS_GLYPH[row.status] || '?' }}</span>
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- Both sides of the edge are work items, so both sides are ways in: the
           reader arrived here to find out what is holding something up, and the
           answer is another item they will want to look at. -->
      <el-table-column label="waiting on" min-width="220">
        <template #default="{ row }">
          <TaskLink v-for="b in row.blocked_by || []" :key="b" :id="b" class="aim-task-link-tag" />
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="perPage" :total="blockedRows.length"
                   :pager-count="7" layout="total, prev, pager, next, jumper"
                   background class="aim-pager" />
    <p class="aim-dim" style="font-size:12px">
      A blocker is an edge in the graph, not a label on a card: it is only a blocker while the item it names
      is not done, which is why this table is computed rather than written down.
    </p>
  </el-card>
</template>

<style>
/* Not scoped: the pager is shared chrome, and one pushed to the end of a
   full-width card is what keeps a bounded list reading as a list. */
.aim-pager { margin-top: 14px; justify-content: flex-end; }
.aim-flow-stats { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; margin-bottom: 10px; }
/* The minute stamp is the join between a row and a bucket on the chart above,
   so it is set in a monospace face: two rows a minute apart have to line up. */
.aim-minute { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.aim-kind-done { color: #34d399; }
.aim-kind-opened { color: #60a5fa; }
.aim-live { color: #34d399; }
.aim-row-fresh { background: rgba(52, 211, 153, .10); }
</style>
