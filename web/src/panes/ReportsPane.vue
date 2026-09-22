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
 * How the board stands, in *two* scopes, folded by the server.
 *
 * The leader's KPI is the done/undone accumulation, and the failure this
 * replaced was subtler than a missing line: the tally was folded here, over
 * `board.tasks`, which is viewer-scoped. A seat that could open 131 of the 139
 * done cards therefore read a *smaller* board than the one that exists and had
 * no way to tell -- the payload already published `withheld_tasks` for exactly
 * that reason, and a count derived client-side from a gated list is the same
 * mistake one level down.
 *
 * So both are read from `reports.board_scope`, which the server folds over
 * `tasks` (visible) and `state["tasks"]` (fabric) and labels. `visible` is the
 * default for the headline, because a reader looking at a page whose tables are
 * gated should see the figure that matches what they can check.
 *
 * This is not derivable from the events above either, and that is why it is a
 * separate tally: `events` counts *moves*, so a card closed before the window
 * opened contributes no event at all. A chart of closes per minute with no line
 * for the work still standing reads as though every minute were progress
 * toward nothing.
 *
 * `blocked` is deliberately not terminal: a blocked item is unfinished, and
 * counting it as finished is the failure this line exists to make visible.
 * `dropped` is excluded from the denominator on the same principle in reverse
 * -- a card someone deliberately dismissed is neither done nor outstanding.
 */
const tally = computed(() => {
  const scope = board.boardScope
  const pick = scope[scopeMode.value] || scope.visible || scope.fabric || undefined
  if (pick) return pick
  // A server that predates `board_scope`. Falling back to the old client-side
  // fold keeps the page readable rather than blank, and `stale: true` in the
  // shell is what says the bundle and the server disagree -- inventing a number
  // silently is the thing this file stopped doing.
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

const SCOPE_LABELS = { visible: 'this view', fabric: 'the whole fabric' }

/** Which scope the headline figures are read in. Both are always on the page. */
const scopeMode = ref('visible')

/**
 * The other scope, so the page can show the number the reader is *not* looking
 * at without switching. `null` when the payload predates the key.
 */
const otherScope = computed(() => {
  const scope = board.boardScope
  const other = scopeMode.value === 'visible' ? 'fabric' : 'visible'
  return scope[other] || null
})

/** How much of the board is finished, in the selected scope. */
const finishedPct = computed(() => tally.value.finished_pct ?? 0)

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

  // The store's own count of closes with a recorded day, and the level the drawn
  // line therefore opens at.
  //
  // The line above is the honest running total *of this window*, and its ceiling
  // is however many cards happened to be closed inside the window -- 43, measured.
  // The leader's question is "how much of the board is done", which is a count of
  // *statuses*, and a line that tops out at 43 is not a smaller version of that
  // answer, it is a different question. So the store-wide line is drawn from
  // `series`, the store's own per-day fold, which counts closes that have a
  // recorded day.
  //
  // It stops short of the headline, and that gap is a fact about the store rather
  // than a defect in the line: 65 closes carry a day and 131 cards carry the done
  // status, because 66 of them were recorded done without a move event to date
  // them. A curve cannot be drawn through a date that does not exist, so the
  // levels are stated on the chart (`doneLevels` below) and the difference is
  // named in words. Drawing the missing 66 as a straight line to today would be
  // the invention this whole file exists to refuse.
  //
  // `carries` is the store's own total minus the window's own closes, rather than
  // the sum of the days before the window opened. The window opens mid-day and a
  // per-day fold cannot say how many of a day's closes landed before noon;
  // subtracting needs no such split and cannot double-count.
  const perDay = board.report.series || []
  const storeCloses = perDay.reduce((n, row) => n + (row.done || 0), 0)
  const carries = Math.max(0, storeCloses - done)
  const closes = cumulative.map((n) => carries + n)

  // The two standing figures the curve cannot reach, as levels on the same axis.
  //
  // `done` is a status and can be set with no event at all; `undone` is not a
  // trajectory either -- it does not move with the window, it is what is left.
  // Both are therefore drawn as reference lines and not as series, because a
  // series invites a reader to watch something move that does not move.
  // `gapped` counts the done cards the recorded-day line cannot carry.
  const doneLevels = {
    done: tally.value.done,
    undone: tally.value.undone,
    gapped: Math.max(0, tally.value.done - storeCloses),
  }

  // The same running total for opens, because one cumulative line says what was
  // finished and nothing says what was started. The gap between the two is the
  // whole reading: where the blue line sits above the green one the window
  // created more than it closed. This is *not* the count of undone work -- a task
  // that existed before the window opened has no event here at all -- and the
  // store-wide line above is what carries the figure that does. Naming the
  // difference is why all three exist.
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
  return { cells, cumulative, openedCumulative, closes, storeCloses, carries, doneLevels,
           start, end: endBucket, opened, done, gap, burst, lastEvent, quietMinutes }
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
  // Twelve readings across whatever width is drawn: with one bucket per minute a
  // 60-minute window otherwise prints sixty overlapping labels and none of them
  // is legible.
  const every = Math.max(0, Math.ceil(f.cells.length / 12) - 1)
  const unit = windowMinutes.value <= 60 ? 'min' : 'window'
  return {
    backgroundColor: 'transparent',
    grid: { left: 52, right: 48, top: 30, bottom: 34 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['opened', 'done', 'closes, the whole store', 'opened cumulative', 'closed cumulative'], top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, interval: every } },
    // One value axis, and the unit is on it.
    //
    // There were two, the running totals on the second one. A second axis is a
    // licence to draw two incomparable things on the same picture, and that is
    // what happened: the store-wide line, drawn on the axis the per-minute bars
    // did not use, was indistinguishable from a series of the rate that happened
    // to climb. Everything here is a count of items, so everything here shares
    // the scale it is counted on, and a reader can compare a bar with a line
    // without reading either axis. The unit says `min` under an hour and
    // `window` over it, because past an hour one bucket is more than a minute
    // and an axis named `items / min` would then be wrong by that factor.
    yAxis: { type: 'value', minInterval: 1, name: `items / ${unit}`, nameTextStyle: { fontSize: 10 },
             splitLine: { lineStyle: { opacity: 0.18 } } },
    // Different mark shapes as well as different colours: the series have to be
    // told apart by a reader who is not being shown the legend's colours.
    series: [
      { name: 'opened', type: 'bar', stack: 'perbucket', symbol: 'circle', symbolSize: 6,
        itemStyle: { color: '#60a5fa' }, barMaxWidth: 10, data: f.cells.map((c) => c.opened) },
      { name: 'done', type: 'bar', stack: 'perbucket', symbol: 'rect', symbolSize: 6,
        itemStyle: { color: '#34d399' }, barMaxWidth: 10, data: f.cells.map((c) => c.done) },
      // The store's closes, drawn as a line, and the one series on this chart
      // whose *height* answers the leader's question rather than only its last
      // point. Its last point is the same number the headline row prints.
      { name: 'closes, the whole store', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 2 }, z: 3, data: f.closes,
        // Three levels, and the one the curve cannot reach is the point. `done`
        // is the headline figure; `undone` is what is left standing; the dotted
        // line under the curve is where the store's dated closes begin, and the
        // distance between that and `done` is the work recorded done with no
        // event to date it. Drawing it as a reference line rather than as a
        // fourth series is honest about what it is: not a trajectory.
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: '#f59e0b', type: 'dotted', width: 1.5 },
          label: { formatter: `${f.carries} closed before this window`, fontSize: 10, position: 'insideStartTop' },
          data: [
            { yAxis: f.doneLevels.done, lineStyle: { color: '#34d399', type: 'dashed', width: 1.5 },
              label: { formatter: `done ${f.doneLevels.done}`, fontSize: 10, position: 'insideEndTop' } },
            { yAxis: f.doneLevels.undone, lineStyle: { color: '#f87171', type: 'dashed', width: 1.5 },
              label: { formatter: `undone ${f.doneLevels.undone}`, fontSize: 10, position: 'insideEndBottom' } },
            { yAxis: f.carries },
          ],
        } },
      // The window's own running totals, still drawn, because the gap between
      // them is the reading a store-wide line cannot give: where the blue line
      // sits above the green one the window created more than it closed.
      { name: 'opened cumulative', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5, type: 'dotted' }, data: f.openedCumulative },
      { name: 'closed cumulative', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#34d399', width: 2 }, data: f.cumulative },
    ],
  }
})

const flowSummary = computed(() => {
  const f = flow.value
  if (!f.opened && !f.done) return ''
  const parts = [`${f.opened} opened and ${f.done} closed in the last ${windowMinutes.value} min, one bucket per minute`]
  // What the drawn line is, and what it is not. A cumulative total over a window
  // counts *events in the window*; the board is a count of statuses. Both are
  // true, they are different numbers, and the reader is told which one is on the
  // chart rather than left to discover it by adding up the columns.
  if (f.closes.length) {
    parts.push(`the curve is the store's dated closes: ${f.carries} before this window, ${f.closes.at(-1)} by the end of it`)
  }
  if (f.doneLevels.gapped) {
    parts.push(`the dashed done line sits ${f.doneLevels.gapped} above the curve, because that many cards carry the done status with no recorded move to date them, and a curve cannot be drawn through a date that does not exist`)
  }
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

  <!-- Both scopes are on the page, and neither is the "real" one: `visible` is
       what this seat can open, `fabric` is everything the store holds. A total
       that changes with who reads it was once reported as the project's figure
       by a consumer that could not tell, so the reader picks, the page names
       which one is being read, and the one not being read is still shown
       underneath rather than hidden behind a toggle nobody presses. -->
  <div class="aim-filterbar" style="margin:0 0 10px">
    <span class="aim-dim" style="font-size:12px">
      Counts are folded by the server in two scopes. The board's cards are gated:
      <strong>{{ board.withheld }}</strong> of <strong>{{ tally.total + board.withheld }}</strong>
      item(s) are withheld from this seat.
    </span>
    <el-radio-group v-model="scopeMode" size="small" data-filter="scope">
      <el-radio-button value="visible">this view</el-radio-button>
      <el-radio-button value="fabric">whole fabric</el-radio-button>
    </el-radio-group>
  </div>

  <p v-if="otherScope" class="aim-dim" style="font-size:12px; margin:0 0 10px">
    In {{ SCOPE_LABELS[scopeMode === 'visible' ? 'fabric' : 'visible'] }}:
    <strong>{{ otherScope.undone }}</strong> undone,
    <strong>{{ otherScope.done }}</strong> done,
    <strong>{{ otherScope.dropped }}</strong> dropped,
    <strong>{{ otherScope.finished_pct }}%</strong> finished
    ({{ otherScope.total }} item(s)).
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
      <!-- The board's standing figures first, and the window's rate after them:
           `undone` is the count the leader reads, and it is the one number on
           this row that a minute-bucket chart cannot draw. -->
      <span><strong>{{ tally.undone }}</strong> undone</span>
      <span><strong>{{ tally.done }}</strong> done</span>
      <span><strong>{{ tally.dropped }}</strong> dropped</span>
      <span><strong>{{ finishedPct }}%</strong> of the board finished</span>
      <span class="aim-dim"><strong>{{ tally.total }}</strong> work item(s) in {{ SCOPE_LABELS[scopeMode] }}</span>
      <span><strong>{{ flow.opened }}</strong> opened in this window</span>
      <span><strong>{{ flow.done }}</strong> closed in this window</span>
      <span><strong>{{ (flow.opened / windowMinutes * 60).toFixed(1) }}</strong> opened / h</span>
      <span><strong>{{ (flow.done / windowMinutes * 60).toFixed(1) }}</strong> closed / h</span>
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
