<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { STATUS_TYPE, color, days, isOverdue, today } from '../theme'

const ctx = inject('ctx')
const board = useBoard()
const drawer = ctx.service('taskDrawer')
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', milestone: 'all', tag: '', onlyLate: false,
})

/**
 * A gantt, drawn by ECharts as a stacked bar: an invisible "offset" series holds
 * each bar at its start date, the visible series is the duration. That recipe is
 * ECharts' own, and it means zoom, tooltip and the today marker come from the
 * library instead of from 120 lines of hand-placed SVG - which is what the
 * previous version of this pane was, and what the leader called 屎.
 */
/**
 * The chart was 62vh for 74 rows, which is 8px a row: the bars were fine and the
 * labels were unreadable, and the leader called it 屎 for the second time. A gantt
 * is a list before it is a chart -- one row per item, one line of text each -- so
 * the height follows the row count and the page scrolls, exactly as the
 * conversation page does. Zooming the x-axis is still the library's job.
 */
const ROW_PX = 21
const CHART_TOP_PX = 16
const CHART_BOTTOM_PX = 56
const CHART_RIGHT_PX = 40

/**
 * Geometry, as a function of the container instead of a literal.
 *
 * Measured off the drawn canvas on the live board (probe-gantt-size.mjs, 8777,
 * `/api/revision` bundle 870b282, payload 161 tasks / 107 dated / 13 day-units):
 *
 *     1440x1000   canvas 1138x2377   gutter 505 = 44.4%   timeline 593 = 52.1%
 *     1024x800    canvas  722x2377   gutter 505 = 69.9%   timeline 177 = 24.5%
 *
 * The gutter is `yAxis.axisLabel.width: 470` plus ECharts' own margins, so it is
 * 505px at both widths, and the timeline is what pays: 4.5px a day at 1024 means
 * a 3-day bar is 13px long against 16px of bar thickness -- a bar taller than it
 * is wide -- and the gutter eats 65% of the chart to get there. It also buys
 * nothing: at this pane's own `11.5px ui-monospace` (6.92px a character) 470px is
 * 67 characters, and the shortest label the pane draws is 66 -- so the same
 * truncation at both widths, which is the one thing width does not change.
 *
 * Every constant below is one of the numbers that used to be hard, and the rule
 * is `ganttGeometry`. The two that decide the shape:
 *
 *  - `DESIGN_MIN_CANVAS_PX`: the label column is budgeted against a canvas we can
 *    design on, not against the one in front of us. A gutter that is a fraction
 *    of the width it is subtracted from has no fixed point (`W - 0.4W` is a
 *    different column at every W) and it is what makes 1024 lose characters that
 *    1440 keeps. Budgeting the *characters* instead gives both widths the same
 *    39, which is what "no label loses more characters at 1024 than at 1440" asks
 *    for; a narrower screen has fewer pixels and cannot be given more.
 *  - `TIMELINE_MIN_PX_PER_DAY`: 24, against the measured 4.5. One day is the
 *    smallest interval the horizon holds, so a day has to be longer than the bar
 *    is thick (`barMaxWidth: 16`) or the chart cannot draw what the card counts.
 *
 * Both were checked against ECharts before they were chosen (probe-gantt-rig.mjs
 * applies this same rule to a real canvas at 5 widths); the widest label in the
 * live payload is 854px and no rule that fits it also keeps a timeline, which is
 * why the budget is a character count and the axis truncates to it.
 */
const MAX_GUTTER_FRACTION = 0.4   // the card's own ceiling on the label column
const MIN_GUTTER_PX = 96          // below this the label column names nothing
const TIMELINE_MIN_PX_PER_DAY = 24
const LABEL_TOP = 4              // ECharts' `axisLabel.margin` for a y-axis
const LABEL_MARGIN = 8           // the gap the label keeps from the bars
const DESIGN_MIN_CANVAS_PX = 720 // the narrowest canvas the gutter is designed on
const TIMELINE_PAD_PX = 6        // ECharts' padding so the first day is not clipped
const MIN_LABEL_PX = 24
const LABEL_FONT = '11.5px ui-monospace, monospace'

/** The whole of the width, as one pure function of a measured number. */
function ganttGeometry(paneWidthPx, dayUnits, charPx) {
  const width = Math.max(1, Math.round(paneWidthPx))
  const labelChars = Math.max(8, Math.floor(
    (DESIGN_MIN_CANVAS_PX * MAX_GUTTER_FRACTION - LABEL_TOP - LABEL_MARGIN) / charPx))
  const labelWanted = labelChars * charPx + LABEL_TOP + LABEL_MARGIN
  // What the timeline needs before the gutter may take anything: 24px a day for
  // every day-unit in the horizon. It is capped by what is left of a pane this
  // narrow, so below ~450px the day shrinks rather than the chart scrolling
  // sideways -- a gantt that scrolls in two directions is a table.
  const timelineFloor = Math.min((dayUnits - TIMELINE_PAD_PX / 2) * TIMELINE_MIN_PX_PER_DAY,
    Math.max(120, width - MIN_GUTTER_PX - CHART_RIGHT_PX))
  const gutterPx = Math.max(MIN_GUTTER_PX,
    Math.min(labelWanted, width * MAX_GUTTER_FRACTION, width - CHART_RIGHT_PX - timelineFloor))
  const timelinePx = width - gutterPx - CHART_RIGHT_PX
  return {
    labelChars,
    gutterPx,
    labelWidthPx: Math.max(MIN_LABEL_PX, gutterPx - LABEL_TOP - LABEL_MARGIN),
    timelinePx,
    pxPerDay: (timelinePx - TIMELINE_PAD_PX) / Math.max(1, dayUnits),
  }
}

/**
 * What the pane measures, and nothing else.
 *
 * `paneWidth` is 0 until the first observation and the option is not built until
 * it is positive: a chart laid out against a width nobody measured is the literal
 * 470 one indirection later. `autoresize` handles the canvas; this handles the
 * *option*, which is the half ECharts cannot do for us.
 */
const chartEl = ref(null)
const paneWidth = ref(0)
const labelCharPx = ref(0)
let sizeObserver = null
let charMeasure = null
const measureLabels = (labels) => {
  if (!charMeasure) {
    charMeasure = document.createElement('canvas').getContext('2d')
    charMeasure.font = LABEL_FONT
  }
  if (!labelCharPx.value) labelCharPx.value = charMeasure.measureText('M').width || 6.9
  return labels.map((label) => charMeasure.measureText(label).width)
}
onMounted(() => {
  if (chartEl.value) {
    paneWidth.value = chartEl.value.clientWidth
    if (typeof ResizeObserver !== 'undefined') {
      sizeObserver = new ResizeObserver((entries) => {
        const box = entries[entries.length - 1]?.contentRect
        if (box && box.width > 0) paneWidth.value = box.width
      })
      sizeObserver.observe(chartEl.value)
    }
  }
  if (!labelCharPx.value) measureLabels([])
})
onBeforeUnmount(() => { sizeObserver?.disconnect(); sizeObserver = null })

/**
 * A header is a claim, and `102 of 102 dated item(s)` was false about 87 of them.
 *
 * Measured on the live board before this: the payload's 159 tasks are 87
 * `seed only (not yet in the store)` and 72 `store only`, and `board.dated` -- the
 * merge -- is 102 rows of which 87 are seeds. A seed has no events at all; its
 * dates are `plan/plan.json`'s text. So the sentence counted the plan file and
 * said "dated item(s)", and the reader had no way to tell that from a record.
 *
 * The authority is named, and it is `board.dated`'s own split rather than a second
 * question: `isPromise` is the store's predicate (`board.js:62`), the same one the
 * landing page counts with. The merged number stays on the page because this pane
 * deliberately draws the merged board -- dropping 87 rows would hide the plan --
 * but it can no longer be read as work.
 */
const datedRecorded = computed(() => allDated.value.filter((t) => !isPromise(t)))
const datedSeeds = computed(() => allDated.value.filter((t) => isPromise(t)))

/**
 * A promise is drawn, and drawn as a promise.
 *
 * Colour here is `color(t.status)` -- a status colour, so a seed whose plan row
 * says `done` was painted the completion green: 42 of the 44 green bars measured
 * on the live board had no events behind them. Two changes, both load-bearing, and
 * both measured in ECharts before they were chosen:
 *
 *  - the promise's fill is the status colour at 32%, because "done" in a plan file
 *    is text and not an outcome. `saturation: -0.5` was the first attempt and it
 *    is *not* a control ECharts honours for a plain colour string -- rendered to
 *    SVG it produced the byte-identical `fill="#34d399"` a recorded bar gets;
 *  - a dashed 1px stroke at the full status colour, the visual grammar a gantt
 *    already uses for "planned / provisional", and a second channel so the mark
 *    does not depend on hue alone.
 *
 * Rendered to SVG, a seed is `fill="rgb(52,211,153)" fill-opacity="0.32"
 * stroke="#34d399" stroke-dasharray="3,3"` against a record's plain `fill`.
 */
const SEED_FILL_ALPHA = 0.32
const fade = (hex, alpha) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}
const barStyle = (task) => (isPromise(task)
  ? { color: fade(color(task.status), SEED_FILL_ALPHA), borderColor: color(task.status),
      borderWidth: 1, borderType: [3, 3], borderRadius: 3 }
  : { color: color(task.status), borderRadius: 3 })

/**
 * The tooltip names provenance, because a bar cannot.
 *
 * Measured on the live board before this: hovering T-0001 rendered
 * `T-0001 Freeze the PM contract… done · codex · high 2026-09-21 → 2026-09-21 (3d
 * estimate) M0` -- byte for byte the shape of a recorded item's tooltip, for a row
 * `/api/state` says the store has never seen. So the tooltip states which authority
 * the status and the dates came from, and says in a clause what that means.
 *
 * It is a named `const` and not an inline arrow inside `option` for one reason: the
 * probe that has to measure this string renders the pane through
 * `vue/server-renderer`, where the only surface is the option object's own
 * properties. A formatter written inline is stripped by any JSON pass over the
 * option; a binding is one the probe can call with a `{ data: { task } }`.
 */
const barTooltip = (p) => {
  const t = p?.data?.task
  if (!t) return ''
  const seed = isPromise(t)
  const when = seed ? 'planned dates' : 'recorded dates'
  return `<b>${t.id}</b> ${t.title}<br/>${t.status} · ${t.owner || 'unassigned'} · ${t.priority || '-'}<br/>`
    + `${when}: ${t.start || '?'} → ${t.due || '?'}${t.estimate ? ` (${t.estimate}d estimate)` : ''}<br/>`
    + (seed
      ? '<i>plan seed, not recorded</i>: this bar is a promise from plan/*.json, '
        + 'there is no work item behind it and no event has ever moved it'
      : 'on the record: this item exists in the store')
    + `${t.milestone ? `<br/>${t.milestone}` : ''}`
}

const allDated = computed(() => board.dated.slice().sort((a, b) => {
    const ka = `${a.milestone || 'zz'}|${a.start || a.due}`
    const kb = `${b.milestone || 'zz'}|${b.start || b.due}`
    return ka < kb ? -1 : ka > kb ? 1 : 0
}))
/**
 * Query filters are shared by the bar list and the header. The rows below call
 * this once; a filtered promise must not disappear from the bars while remaining
 * in the denominator, or the header answers a different question than the chart.
 */
const matches = (task) => {
  if (filters.q) {
    const needle = filters.q.toLowerCase()
    if (!`${task.id} ${task.title} ${task.accept || ''}`.toLowerCase().includes(needle)) return false
  }
  if (filters.owner && task.owner !== filters.owner) return false
  if (filters.status && task.status !== filters.status) return false
  if (filters.milestone !== 'all' && task.milestone !== filters.milestone) return false
  if (filters.tag && !(task.tags || []).includes(filters.tag)) return false
  if (filters.onlyLate && !isOverdue(task.due, task.status, board.terminal)) return false
  return true
}
const milestones = computed(() => [...new Set(board.dated.map((t) => t.milestone).filter(Boolean))].sort())

/**
 * The rows are the bars; the promise count is not the row count.
 *
 * `drawn` exists because the header has to say how much of the drawn set is work,
 * and a filter is exactly where the two diverge: measured by narrowing to one id,
 * the old header read `1 of 107 dated item(s)` with no way to tell whether the one
 * row was a promise. `rows` and `drawn` apply the same predicate to the same list,
 * so a filter cannot move one without the other.
 */
const rowOf = (t, first) => ({
  task: t,
  label: `${first && t.milestone ? `${t.milestone} ▏` : '   '}${t.id} · ${t.title.length > 62 ? t.title.slice(0, 61) + '…' : t.title}`,
})
const allRows = computed(() => {
  const seen = new Set()
  return allDated.value.map((t) => {
    const first = !seen.has(t.milestone)
    seen.add(t.milestone)
    return rowOf(t, first)
  })
})
const rows = computed(() => allRows.value.filter((r) => matches(r.task)))
const drawn = computed(() => rows.value.filter((r) => !isPromise(r.task)).length)
const span = computed(() => {
  const [lo, hi] = board.horizon
  return { lo, hi, n: Math.max(1, days(lo, hi) + 2) }
})

/**
 * The measured width, and the option it produces.
 *
 * Every number the y-axis and the grid are built from comes out of `geometry`,
 * which is a function of `paneWidth` -- so there is no pixel in this pane that
 * cannot move when the container does. The `if (!geometry.value) return {}` is
 * load-bearing: on the first render the pane has not been measured, and an
 * option built then would be a chart laid out against an assumed width.
 */
const labels = computed(() => rows.value.map((r) => r.label))
const labelWidths = computed(() => measureLabels(labels.value))
const geometry = computed(() => (paneWidth.value > 0
  ? ganttGeometry(paneWidth.value, span.value.n, labelCharPx.value || 6.9)
  : null))

/**
 * The height, bounded by the screen the chart is read on.
 *
 * `rows * ROW_PX + 130` is the height the content wants, and at 107 rows that is
 * 2377px inside a 951px scroller -- 2.3x the screen, measured. The consequence is
 * in the card: a click at half the canvas height lands outside the viewport, and
 * the click target's position is a function of how oversized the canvas is, so
 * the pane's interaction degrades exactly in proportion to a number nobody
 * chose. The reader's own window is the bound instead: the card gets what the
 * scroller has, minus the room a list needs to still be a list (the sticky head
 * and one row of context). Below `MIN_CHART_PX` a chart is not a chart, so that
 * is the floor even when the window is smaller than the rule.
 *
 * The chart is then taller than its box and the *box* scrolls, which is what
 * gives back a bounded click target: the y-axis is clipped to the same window as
 * the bars, so the label the reader clicks and the row that opens are in the
 * same coordinate space again (T-0189's second half; `yZoom` is the other way to
 * get there and it costs the axis).
 */
const MAX_CHART_PX = 1600
const MIN_CHART_PX = 320
const chartWindow = ref(0)
const contentHeight = computed(() => rows.value.length * ROW_PX + CHART_TOP_PX + CHART_BOTTOM_PX)
const chartHeight = computed(() => Math.round(Math.max(MIN_CHART_PX,
  Math.min(contentHeight.value, MAX_CHART_PX, chartWindow.value || MAX_CHART_PX))))

/**
 * The window the pane shows the chart through, measured from the app's own
 * scroller rather than assumed from `window.innerHeight`.
 *
 * `.aim-main` is the shell's scroller and it has a height of its own (the shell
 * is a flex column), so its `clientHeight` does not change when this pane's
 * content does -- which is what makes this the one measurement that cannot feed
 * back into itself. The sticky card header is measured too, and four rows are
 * left over the fold so the list still reads as a list with something below it.
 */
function measureWindow() {
  const scroller = chartEl.value?.closest('.aim-main')
  const head = chartEl.value?.closest('.el-card')?.querySelector('.el-card__header')
  const viewport = scroller ? scroller.clientHeight : (window.innerHeight || 0)
  const headH = head ? head.getBoundingClientRect().height : 0
  chartWindow.value = Math.max(MIN_CHART_PX, Math.round(viewport - headH - ROW_PX * 4))
}
let windowObserver = null
const onViewportResize = () => measureWindow()
onMounted(() => {
  measureWindow()
  window.addEventListener('resize', onViewportResize)
  const scroller = chartEl.value?.closest('.aim-main')
  if (scroller && typeof ResizeObserver !== 'undefined') {
    windowObserver = new ResizeObserver(onViewportResize)
    windowObserver.observe(scroller)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onViewportResize)
  windowObserver?.disconnect()
  windowObserver = null
})

const option = computed(() => {
  const { lo, n } = span.value
  const g = geometry.value
  if (!g || !rows.value.length) return {}
  const offsets = rows.value.map((r) => {
    const start = r.task.start || r.task.due
    return Math.max(0, days(lo, start))
  })
  const bars = rows.value.map((r) => {
    const start = r.task.start || r.task.due
    const end = r.task.due || r.task.start
    const dur = Math.max(1, days(start, end) + 1)
    return { value: dur, itemStyle: barStyle(r.task), task: r.task }
  })
  return {
    backgroundColor: 'transparent',
    // `containLabel: true` measures the labels ECharts was handed; the label
    // width below is the budget, so `left` is the pad between them and the edge.
    grid: { left: 4, right: CHART_RIGHT_PX, top: CHART_TOP_PX, bottom: CHART_BOTTOM_PX, containLabel: true },
    tooltip: { trigger: 'item', formatter: barTooltip },
    xAxis: {
      type: 'value', min: 0, max: n, position: 'top',
      axisLabel: {
        formatter: (v) => {
          const d = new Date(Date.parse(lo) + v * 86400000)
          return `${d.getMonth() + 1}/${d.getDate()}`
        },
      },
      splitLine: { show: true, lineStyle: { opacity: 0.18 } },
    },
    yAxis: {
      type: 'category', inverse: true,
      data: labels.value,
      // The gutter, as a number the container chose: a character budget
      // (`g.labelChars`), measured in this pane's own font, minus what the axis
      // itself spends on margins.
      axisLabel: {
        width: g.labelWidthPx, overflow: 'truncate',
        fontSize: 11.5, fontFamily: 'ui-monospace, monospace',
      },
      axisTick: { show: false },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'weakFilter' },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8, filterMode: 'weakFilter' },
    ],
    series: [
      { name: 'offset', type: 'bar', stack: 'gantt', silent: true, itemStyle: { color: 'transparent' }, data: offsets },
      {
        // no per-bar label: a one-day bar is twelve pixels wide and the status
        // text on it was noise. The status is in the colour, the legend and the
        // tooltip, which is where it can actually be read.
        name: 'duration', type: 'bar', stack: 'gantt', barMaxWidth: 16, data: bars,
        markLine: {
          symbol: 'none', silent: true,
          data: [{ xAxis: days(lo, today()) }],
          lineStyle: { color: '#ef4444', type: 'dashed' },
          label: { formatter: 'today', color: '#ef4444' },
        },
      },
    ],
  }
})
function onClick(p) {
  if (p.data?.task) drawer.open(p.data.task.id, { tasks: board.tasks })
}
const undated = computed(() => board.tasks.filter((t) => !t.start && !t.due && matches(t)))
/** The undated list's own split, so its sentence cannot describe the wrong half. */
const undatedRecorded = computed(() => undated.value.filter((t) => !isPromise(t)).length)
const undatedSeeds = computed(() => undated.value.filter((t) => isPromise(t)).length)
</script>

<template>
  <el-card shadow="never" class="aim-sticky-head">
    <template #header>
      <div class="aim-filterbar">
        <!-- The claim is split into the two universes it always mixed, and each
             number says which one it is about. "102 of 102 dated item(s)" was false
             about 87 of its 102: a seed has no events, so nothing moved it and it is
             not work. The merged denominator stays -- this pane deliberately draws
             the merged board, and hiding 87 rows would hide the plan -- but the
             board's split is stated over the board, and the filter count is stated
             apart from it, so no clause counts one universe and describes another
             (the defect the Plan pane's undated sentence had). -->
        <span :data-recorded="datedRecorded.length" :data-seeds="datedSeeds.length" :data-drawn="drawn">
          timeline — {{ rows.length }} shown; of {{ allDated.length }} dated bar(s),
          <b>{{ datedRecorded.length }}</b> on the record and {{ datedSeeds.length }}
          <span class="aim-chip seed">plan seeds</span> (promises, not work), {{ span.lo }} → {{ span.hi }}</span>
        <el-input v-model="filters.q" size="small" placeholder="search id, title, acceptance" clearable />
        <el-select v-model="filters.owner" size="small" placeholder="owner" clearable>
          <el-option v-for="owner in board.owners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-select v-model="filters.status" size="small" placeholder="status" clearable>
          <el-option v-for="status in board.statuses" :key="status" :value="status" :label="status" />
        </el-select>
        <el-select v-model="filters.milestone" size="small" placeholder="milestone">
          <el-option value="all" label="every milestone" />
          <el-option v-for="m in milestones" :key="m" :value="m" :label="m" />
        </el-select>
        <el-select v-model="filters.tag" size="small" placeholder="tag" clearable>
          <el-option v-for="tag in board.tags" :key="tag" :value="tag" :label="tag" />
        </el-select>
        <el-checkbox v-model="filters.onlyLate">overdue only</el-checkbox>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <span style="flex:1" />
        <!-- The one non-status mark on the chart, drawn as the bar draws it: a
             reader who has not hovered anything has to be able to decode it. It
             is inline-styled and not a class, because the fill it samples is the
             same `barStyle` the series uses and a stylesheet copy of it is the
             second answer this project keeps finding. -->
        <span style="display:flex;align-items:center;gap:4px;font-size:11.5px">
          <span :style="{ width: '18px', height: '9px', borderRadius: '2px', display: 'inline-block',
                          background: 'rgb(148 163 184 / .3)', border: '1px dashed rgb(148 163 184)' }" />
          <span class="aim-dim">plan seed</span>
        </span>
        <span v-for="st in board.statuses" :key="st" style="display:flex;align-items:center;gap:4px;font-size:11.5px">
          <span :style="{ width: '9px', height: '9px', borderRadius: '2px', background: color(st) }" />
          <span class="aim-dim">{{ st }}</span>
        </span>
        <span class="aim-dim" style="font-size:12px">drag inside the chart to zoom, or use the slider below</span>
      </div>
    </template>
    <VChart v-if="rows.length" :option="option" autoresize
            :style="{ height: chartHeight + 'px' }" @click="onClick" />
    <el-empty v-else description="no dates anywhere: every bar in a gantt is a promise, and this plan has not made one yet" />
  </el-card>

  <el-card v-if="undated.length" shadow="never" style="margin-top:14px">
    <!-- This said "they are work with no promise attached", and the count is over
         `board.tasks` -- the merge. An undated *seed* is the exact opposite: it is
         all promise and no work. Measured on this branch's payload: the undated
         items split 0 seeds / 57 recorded, so the sentence happened to be true of
         100% of its count by luck, and a plan row added without dates would have
         made it false. Both halves are named here, like the header. -->
    <template #header>{{ undated.length }} item(s) with no dates, so no bar:
      <b>{{ undatedRecorded }}</b> on the record{{ undatedSeeds ? `, ${undatedSeeds} plan seeds (a promise with no date is not work)` : '' }}</template>
    <el-tag v-for="t in undated" :key="t.id" size="small" effect="plain" style="margin:2px" :type="STATUS_TYPE[t.status] || 'info'">
      {{ t.id }}
    </el-tag>
  </el-card>

</template>
