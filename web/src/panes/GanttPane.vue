<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { isPromise, useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import TaskLink from '../components/TaskLink.vue'
import { color, days, isOverdue, today } from '../theme'

const ctx = inject('ctx')
const board = useBoard()
const drawer = ctx.service('taskDrawer')
// `per` is the family's key, shared with Items and Kanban, so a reader who sets a
// page size on one list finds it on the next (T-0161 clause 1).
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', milestone: 'all', tag: [], onlyLate: false, per: '25',
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
 *    It is the *aspiration* the pane spends when it has the width; the floor that
 *    binds is below.
 *  - `TIMELINE_MIN_PX`: 360, which is the 151 measured at 1024 held to a floor of
 *    its own. It is spent *before* the gutter, so the two cannot trade; what the
 *    pane cannot fit is scroll (T-0189), not truncation (T-0161 clause 3).
 *
 * The rest were checked against ECharts before they were chosen (probe-gantt-rig.mjs
 * applies this same rule to a real canvas at 5 widths); the widest label in the
 * live payload is 854px and no rule that fits it also keeps a timeline, which is
 * why the budget is a character count and the axis truncates to it.
 *
 * The one thing the character budget got wrong is that it still spent the *labels*
 * to buy the timeline: `/api/revision` at 1024 was a 151px timeline against a
 * 505px gutter at 1440, and 88 labels truncated at both. The timeline is a
 * quantity with a floor (T-0161 clause 3), so it is no longer a remainder --
 * `TIMELINE_MIN_PX` is deducted first and the canvas grows past the pane when the
 * two cannot both fit. The pane owns an `overflow-x: auto` box, so the width the
 * reader pays for is the width the chart gets, and the label column stops being
 * the thing that is negotiated: it wraps to a second line instead of losing
 * characters, and one row is still one item.
 */
const MAX_GUTTER_FRACTION = 0.4   // the card's own ceiling on the label column
const MIN_GUTTER_PX = 96          // below this the label column names nothing
const TIMELINE_MIN_PX = 360       // the timeline's own floor, against the measured 151
const LABEL_TOP = 4              // ECharts' `axisLabel.margin` for a y-axis
const LABEL_MARGIN = 8           // the gap the label keeps from the bars
const DESIGN_MIN_CANVAS_PX = 720 // the width the label column is budgeted against
const TIMELINE_PAD_PX = 6        // ECharts' padding so the first day is not clipped
const MIN_LABEL_PX = 24
const LABEL_FONT = '11.5px ui-monospace, monospace'

/**
 * The whole of the width, as one pure function of a measured number.
 *
 * Two of the three terms are now independent of `paneWidthPx`: the gutter is a
 * character budget measured in this pane's font, and the timeline is a floor. The
 * measured width only decides how much timeline is there to *spend* above the
 * floor, and `canvasPx` is what those three add up to -- which is the number the
 * chart is drawn at, and the number the scroller scrolls to.
 */
function ganttGeometry(paneWidthPx, dayUnits, charPx) {
  const width = Math.max(1, Math.round(paneWidthPx))
  const labelChars = Math.max(8, Math.floor(
    (DESIGN_MIN_CANVAS_PX * MAX_GUTTER_FRACTION - LABEL_TOP - LABEL_MARGIN) / charPx))
  const labelWanted = labelChars * charPx + LABEL_TOP + LABEL_MARGIN
  const gutterPx = Math.max(MIN_GUTTER_PX, labelWanted)
  // What the horizon wants and what is left of the pane, whichever is larger: a
  // day-unit stays 24px wide as long as the pane can afford it, and a narrow pane
  // scrolls rather than compressing the axis below the floor.
  const timelinePx = Math.max(TIMELINE_MIN_PX, width - gutterPx - CHART_RIGHT_PX)
  return {
    labelChars,
    gutterPx,
    labelWidthPx: Math.max(MIN_LABEL_PX, gutterPx - LABEL_TOP - LABEL_MARGIN),
    timelinePx,
    canvasPx: Math.ceil(gutterPx + CHART_RIGHT_PX + timelinePx),
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
/**
 * A promise is drawn in its own lane, because a mark inside a shared row is a
 * mark the reader has to have been told about.
 *
 * The dashed hollow bar above is right about the *fill* and wrong about the
 * *row*: a seed and a record for the same period still occupy two adjacent rows
 * that look like two items of the same kind, and the card's complaint is that 87
 * plan rows read as work. A lane is the shape that cannot be misread -- a lane is
 * a section with one kind of thing in it, and the row's own text says which lane
 * it is in. The chart's own `legend` is the control: it toggles a whole lane.
 */
const LANES = [
  { key: 'promise', label: 'plan promises — plan/*.json, not work' },
  { key: 'recorded', label: 'recorded work — in the store' },
]
const laneOf = (task) => (isPromise(task) ? 'promise' : 'recorded')
/**
 * The lane's mark, in one place, because it is drawn on three surfaces.
 *
 * The glyph was written twice -- the row label (`rowOf`) and the undated tags --
 * and absent from the third. The tooltip does name the authority in words
 * (`planned dates` / `plan seed, not recorded`), but a reader who has learned the
 * mark from the labels is the reader this mark is for -- the one who cannot tell
 * the lanes apart by colour -- and the tooltip handed them a different vocabulary
 * at the moment the row explaining it was under the pointer. One derivation, so
 * the three surfaces cannot drift apart.
 */
const laneMark = (task) => (isPromise(task) ? '◌' : '●')
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
  return `${laneMark(t)} <b>${t.id}</b> ${t.title}<br/>${t.status} · ${t.owner || 'unassigned'} · ${t.priority || '-'}<br/>`
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
  // T-0166: every selected tag has to be on the item. This surface held a single
  // value (`tag: ''` and `includes(filters.tag)`), so a second pick *replaced*
  // the first and `?tag=alpha&tag=beta` showed the union -- measured on the bundle
  // this replaces. Items and Kanban were already `.every(...)`; the three surfaces
  // now share one rule, which is what the card asks for.
  if (filters.tag.length && !filters.tag.every((tag) => (task.tags || []).includes(tag))) return false
  if (filters.onlyLate && !isOverdue(task.due, task.status, board.terminal)) return false
  return true
}
const milestones = computed(() => [...new Set(board.dated.map((t) => t.milestone).filter(Boolean))].sort())

/**
 * The three numbers the header publishes, and which list each is over.
 *
 * `data-drawn` is the total the filter leaves -- every dated row the chart is asked
 * to draw -- and `data-recorded` and `data-seeds` are that same set split by
 * `isPromise`. So the three are one statement rather than three: `drawn` is
 * `recorded` + `seeds`, and the split is what the header's sentence is about.
 *
 * That is a fix, and the defect it fixes is one the attribute's own name carried.
 * `drawn` was `rows.filter((r) => !isPromise(r.task)).length`, i.e. the *recorded*
 * rows -- so `data-drawn` published `data-recorded` under a second name, and on any
 * board with no filter and fewer rows than the page size the two were the same
 * number. Measured on the live board: 107 dated rows, `data-drawn` 20 and
 * `data-recorded` 20; `?status=done` gave 17 and 20, `?owner=codex` 2 and 20,
 * `?milestone=M1` 0 and 20 -- a number that is *called* drawn and answers "how many
 * of these are recorded work" is the second answer to a question the element already
 * answers beside it. `recorded-vs-seed.spec.js` reads it as the total and expects 11
 * on a fixture where 11 dated rows are drawn; the pane answered 3.
 *
 * The sentence itself is unchanged and was never wrong: it prints `rows.length` for
 * the shown count and the split for the two halves. Only the attribute was ever
 * saying the wrong thing, and it was saying it twice.
 *
 * The row text carries the lane as well (`◌` promise, `●` recorded). The legend
 * names the lanes and toggles them, but a legend is at the top of a 1600px chart
 * and the reader is at row 90; the glyph travels with the row.
 */
const rowOf = (t, first) => ({
  task: t,
  label: `${laneMark(t)} ${first && t.milestone ? `${t.milestone} ▏` : '  '}${t.id} · ${t.title.length > 62 ? t.title.slice(0, 61) + '…' : t.title}`,
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
/** Every dated row the filter leaves: what the chart is asked to draw. */
const drawn = computed(() => rows.value.length)

/**
 * The bound on the list, and it is the reader's (T-0161 clause 1).
 *
 * `?per=` is the family's key -- Items and Kanban read the same one -- so the page
 * size is in the URL and survives a filter change. The options are derived from
 * the payload rather than taken from the query: `?per=99999` pasted by hand would
 * otherwise unbind the page it exists to bound, and `Number('x')` is NaN with a
 * NaN slice drawn. Two lanes page independently below, so `per` counts *rows of
 * the timeline* and each lane gets the same window; a lane is a section, not a
 * filter.
 */
const PAGE_SIZES = [25, 50, 100]
const perPage = computed(() => {
  const n = Number(filters.per)
  return PAGE_SIZES.includes(n) ? n : PAGE_SIZES[0]
})
const page = ref(0)
const shownRows = computed(() => rows.value.slice(page.value * perPage.value, (page.value + 1) * perPage.value))
watch(() => [filters.q, filters.owner, filters.status, filters.milestone, filters.tag, filters.onlyLate],
  () => { page.value = 0 })
watch([rows, perPage], () => {
  const last = Math.max(0, Math.ceil(rows.value.length / perPage.value) - 1)
  if (page.value > last) page.value = last
})

/**
 * The lanes are windows on the same page, not two different lists.
 *
 * A gantt row cannot say which of the two universes it belongs to by its y
 * position alone, so the lanes are sections of one axis, in the order a plan is
 * read (promises, then work), and each lane is its own ECharts series so the
 * chart's own legend can toggle it.
 */
const laneRows = computed(() => LANES.map((lane) => ({
  ...lane,
  rows: shownRows.value.filter((r) => laneOf(r.task) === lane.key),
})).filter((lane) => lane.rows.length))
const lanesHidden = ref({})
const onLegendToggle = (p) => { lanesHidden.value = { ...lanesHidden.value, [p.name]: !p.selected?.[p.name] } }

/**
 * One axis category per bar, and one blank category for each lane break.
 *
 * Every row keeps its text: the gutter wraps now, so a longer label costs a line
 * and not the characters after it, and a row with no text is a row the reader
 * cannot name (which is the half of T-0189 that "truncates 88 labels" is about).
 * The lane break is the single empty category, and it is one row tall, which is
 * the gap that makes two lanes read as two lanes.
 */
const ticks = computed(() => {
  const marks = []
  for (const lane of laneRows.value) {
    if (marks.length) marks.push('')
    marks.push(...lane.rows.map((r) => r.label))
  }
  return marks
})
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
 *
 * `labelWidths` is no longer consulted for the axis width -- the axis width is
 * the gutter `ganttGeometry` spent, and `overflow: 'break'` wraps inside it. It
 * survives because the *height* is what a wrapped label changes, and the pane
 * still measures the strings to know which rows are two lines.
 */
const labels = computed(() => ticks.value)
const labelWidths = computed(() => measureLabels(labels.value.filter(Boolean)))
const geometry = computed(() => (paneWidth.value > 0
  ? ganttGeometry(paneWidth.value, span.value.n, labelCharPx.value || 6.9)
  : null))
const wrappedRows = computed(() => labelWidths.value.reduce((n, w) => n
  + Math.max(0, Math.ceil(w / Math.max(MIN_LABEL_PX, (geometry.value?.labelWidthPx || MIN_LABEL_PX))) - 1), 0))

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
// One row per axis category, plus the extra lines a wrapped label costs: the
// gutter wraps rather than truncating now, and a row that took two lines is two
// rows of pixels on the canvas. Measuring the height off `ticks` and not `rows`
// is what keeps the last row inside the chart instead of under the slider.
const contentHeight = computed(() => (ticks.value.length + wrappedRows.value) * ROW_PX
  + CHART_TOP_PX + CHART_BOTTOM_PX)
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

/**
 * The chart, as two lanes on one axis.
 *
 * ECharts has no grouped stack: `stack` is global, so two lanes need their own
 * band between them -- the lane break below. It is not decoration, it is one row
 * of height and the only reason a promise's bar and a record's bar are not
 * adjacent pixels; the height comes from the axis, so the break is a category the
 * options must give a label and a value to.
 *
 * Both series carry an entry per axis category, including the break, because a
 * bar series draws `data[i]` against category `i`: an array that skipped the
 * break would draw its lane at the top of the axis while the offsets sat below.
 * The lane's own legend entry is its bar series and `selected` is the toggle
 * state, so hiding a lane hides the bars the reader was looking at.
 *
 * The lead-in is one entry per category *before* the lane, not one entry.
 *
 * A lane that is not the first has to skip the categories the earlier lanes and
 * the break already own, and the number to skip is theirs, not one. This emitted a
 * single zero, so the second lane's bars were drawn from category 1: measured on
 * the served bundle with the T-0188 fixture, the promise lane's rows sat in
 * categories 0..7 and the recorded lane's three bars were painted into categories
 * 1, 2, 3 -- the rows of T-9002, T-9003 and T-9004 -- while the rows they belong to
 * (T-9009, T-9010, T-9011) carried no label at all. A census of the canvas agrees
 * with the index arithmetic: the recorded bar's opaque run is inside the promise
 * bar's row. The one-lane case is unchanged (the lead is empty), which is why a
 * fixture with only records always looked right.
 */
const option = computed(() => {
  const { lo, n } = span.value
  const g = geometry.value
  if (!g || !laneRows.value.length) return {}
  const offsets = []
  const series = []
  const breakAt = () => {
    offsets.push({ value: n, itemStyle: { color: 'transparent' }, silent: true })
  }
  // How many categories this lane starts after: every earlier lane's rows plus one
  // for each break between them. It is advanced by this lane's own rows at the
  // bottom of the loop, so it is the lane's own first category at the top.
  let at = 0
  laneRows.value.forEach((lane) => {
    if (series.length) { breakAt(); at += 1 }
    offsets.push(...lane.rows.map((r) => ({
      value: Math.max(0, days(lo, r.task.start || r.task.due)),
      itemStyle: { color: 'transparent' }, silent: true,
    })))
    series.push({
      name: lane.label, type: 'bar', stack: 'gantt', barMaxWidth: 16,
      data: [
        // The lead-in's bars are zero-width and they still carry the transparent
        // style, so they draw nothing at any bar width the axis chooses.
        ...Array.from({ length: at }, () => ({ value: 0, itemStyle: { color: 'transparent' } })),
        ...lane.rows.map((r) => {
          const start = r.task.start || r.task.due
          const end = r.task.due || r.task.start
          return { value: Math.max(1, days(start, end) + 1), itemStyle: barStyle(r.task), task: r.task }
        }),
      ],
    })
    at += lane.rows.length
  })
  return {
    backgroundColor: 'transparent',
    // `containLabel: true` measures the labels ECharts was handed; the label
    // width below is the budget, so `left` is the pad between them and the edge.
    grid: { left: 4, right: CHART_RIGHT_PX, top: CHART_TOP_PX, bottom: CHART_BOTTOM_PX, containLabel: true },
    tooltip: { trigger: 'item', formatter: barTooltip },
    legend: {
      data: laneRows.value.map((lane) => lane.label),
      selected: lanesHidden.value,
      top: 0, right: CHART_RIGHT_PX, itemWidth: 18, itemHeight: 9,
      textStyle: { fontSize: 11.5 },
    },
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
      // itself spends on margins. `overflow: 'break'` rather than `truncate` is
      // T-0161 clause 3: a label that does not fit wraps, and one row that needs
      // two lines is two lines rather than a row with the id on it and the title
      // cut off.
      axisLabel: {
        width: g.labelWidthPx, overflow: 'break',
        fontSize: 11.5, fontFamily: 'ui-monospace, monospace', lineHeight: 13,
      },
      axisTick: { show: false },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'weakFilter' },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8, filterMode: 'weakFilter' },
    ],
    series: [
      // The offset series is invisible and carries the row's task, which is what
      // `onClick` opens and what the tooltip reads; the visible series is the
      // duration. Both are one stack, so the lane order is the row order.
      { name: 'offset', type: 'bar', stack: 'gantt', silent: true, itemStyle: { color: 'transparent' }, data: offsets },
      ...series,
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
// Closed by default: 57 tags is a wall, and the header already says how many and
// of which kind. The loader is the button and the header count is the reason to
// press it.
const undatedOpen = ref(false)
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
        <el-select v-model="filters.tag" size="small" placeholder="tag" multiple collapse-tags clearable>
          <el-option v-for="tag in board.tags" :key="tag" :value="tag" :label="tag" />
        </el-select>
        <!-- The list's bound, and the reader's: the same `per` key Items and Kanban
             read, so a page size set on one list is set on the next. -->
        <el-select v-model="filters.per" size="small" placeholder="per page" data-filter="per"
                   style="width:112px">
          <el-option v-for="size in PAGE_SIZES" :key="size" :value="String(size)" :label="`${size} rows`" />
        </el-select>
        <el-checkbox v-model="filters.onlyLate">overdue only</el-checkbox>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <span style="flex:1" />
        <!-- The one non-status mark on the chart, drawn as the bar draws it: a
             reader who has not hovered anything has to be able to decode it. It
             is inline-styled and not a class, because the fill it samples is the
             same `barStyle` the series uses and a stylesheet copy of it is the
             second answer this project keeps finding. The chart carries the lane
             legend itself (it toggles the lanes); this chip is the same promise
             mark next to the filters, so a dashed hollow bar is never an
             unexplained mark. -->
        <span style="display:flex;align-items:center;gap:4px;font-size:11.5px">
          <span :style="{ width: '18px', height: '9px', borderRadius: '2px', display: 'inline-block',
                          background: 'rgb(148 163 184 / .3)', border: '1px dashed rgb(148 163 184)' }" />
          <span class="aim-dim">◌ plan promise, not work · ● recorded work</span>
        </span>
        <span v-for="st in board.statuses" :key="st" style="display:flex;align-items:center;gap:4px;font-size:11.5px">
          <span :style="{ width: '9px', height: '9px', borderRadius: '2px', background: color(st) }" />
          <span class="aim-dim">{{ st }}</span>
        </span>
        <span class="aim-dim" style="font-size:12px">drag inside the chart to zoom, or use the slider below</span>
      </div>
    </template>
    <!-- The width the chart is drawn at is the chart's own (`geometry.canvasPx`),
         not the box's, so the timeline keeps its floor and this box scrolls
         sideways instead of the page body. The y-axis labels scroll with it: the
         chart is one canvas, and a second sticky copy of the label column is the
         table this pane is not. -->
    <div v-if="rows.length" ref="chartEl" class="aim-gantt-scroll">
      <VChart :option="option" autoresize @click="onClick"
              :style="{ height: chartHeight + 'px', width: (geometry?.canvasPx || 0) + 'px' }"
              @legendselectchanged="onLegendToggle" />
    </div>
    <el-empty v-else description="no dates anywhere: every bar in a gantt is a promise, and this plan has not made one yet" />
    <!-- The bound, stated rather than implied, like the Items list's. Both lanes
         are windows on the same page, so this counts rows of the timeline and not
         rows of one lane. -->
    <el-pagination v-if="rows.length" :current-page="page + 1" :page-size="perPage" :total="rows.length"
                   :pager-count="7" layout="total, prev, pager, next, jumper" background
                   class="aim-pager" @current-change="(p) => { page = p - 1 }" />
  </el-card>

  <el-card v-if="undated.length" shadow="never" style="margin-top:14px">
    <!-- This said "they are work with no promise attached", and the count is over
         `board.tasks` -- the merge. An undated *seed* is the exact opposite: it is
         all promise and no work. Measured on this branch's payload: the undated
         items split 0 seeds / 57 recorded, so the sentence happened to be true of
         100% of its count by luck, and a plan row added without dates would have
         made it false. Both halves are named here, like the header.

         The tags are behind a count and a link (T-0161 clause 3): 57 tags is a
         wall, and a wall is not a list. The count and the link are the same
         number, so the header answers "how many" and the button answers "show me"
         without either of them lying.

         The id is a `TaskLink`, not text: this list is where a reader is most
         likely to be looking for a way in, because an item with no dates has no
         bar to click either, and an id drawn as text here is the dead end that
         component exists to remove. `laneMark` rides in the link's label, the same
         glyph the row labels and the chip above use. The tag's `type` -- a status
         colour -- did not survive the swap: this pane's header states the split in
         words, and a colour on a control that opens a drawer is a claim the reader
         cannot act on. -->
    <template #header>{{ undated.length }} item(s) with no dates, so no bar:
      <b>{{ undatedRecorded }}</b> on the record{{ undatedSeeds ? `, ${undatedSeeds} plan seeds (a promise with no date is not work)` : '' }}</template>
    <el-button size="small" text @click="undatedOpen = !undatedOpen">
      {{ undatedOpen ? 'hide the list' : `show all ${undated.length}` }}
    </el-button>
    <span v-if="!undatedOpen" class="aim-dim" style="font-size:12px;margin-left:6px">
      ({{ undatedRecorded }} recorded · {{ undatedSeeds }} promises)
    </span>
    <div v-if="undatedOpen" class="aim-undated-tags">
      <TaskLink v-for="t in undated" :key="t.id" :id="t.id" :label="`${laneMark(t)} ${t.id}`"
                class="aim-task-link-tag" />
    </div>
  </el-card>

</template>

<style>
/* Not scoped: `style.css` is another task's file this round, and a chart whose
   own width is a scroll is a property of the box, not of the pane's markup. */
.aim-gantt-scroll { overflow-x: auto; overflow-y: hidden; }
/* The wall the count/link guards is still a wall when it is drawn: these wrap, and
   `style.css`'s `.aim-task-link-tag` is a right-margin built for a row of blockers,
   which spaces a wrapped run of 57 links on one axis only. */
.aim-undated-tags .aim-task-link-tag { margin: 2px; display: inline-block; }
</style>
