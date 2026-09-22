<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import TaskDecisionDrawer from '../components/TaskDecisionDrawer.vue'
import { STATUS_TYPE, color, days, isOverdue, today } from '../theme'

const board = useBoard()
const selected = ref(null)
const drawer = ref(false)
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
const allDated = computed(() => board.dated.slice().sort((a, b) => {
    const ka = `${a.milestone || 'zz'}|${a.start || a.due}`
    const kb = `${b.milestone || 'zz'}|${b.start || b.due}`
    return ka < kb ? -1 : ka > kb ? 1 : 0
}))
const milestones = computed(() => [...new Set(board.dated.map((t) => t.milestone).filter(Boolean))].sort())
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
const rows = computed(() => {
  const dated = allDated.value.filter(matches)
  const seen = new Set()
  return dated.map((t) => {
    const first = !seen.has(t.milestone)
    seen.add(t.milestone)
    const label = `${t.id} · ${t.title.length > 62 ? t.title.slice(0, 61) + '…' : t.title}`
    return { task: t, label: first && t.milestone ? `${t.milestone} ▏${label}` : `   ${label}` }
  })
})
const chartHeight = computed(() => Math.min(3000, Math.max(320, rows.value.length * ROW_PX + 130)))
const span = computed(() => {
  const [lo, hi] = board.horizon
  return { lo, hi, n: Math.max(1, days(lo, hi) + 2) }
})
const option = computed(() => {
  const { lo, n } = span.value
  const offsets = rows.value.map((r) => {
    const start = r.task.start || r.task.due
    return Math.max(0, days(lo, start))
  })
  const bars = rows.value.map((r) => {
    const start = r.task.start || r.task.due
    const end = r.task.due || r.task.start
    const dur = Math.max(1, days(start, end) + 1)
    return { value: dur, itemStyle: { color: color(r.task.status), borderRadius: 3 },
             task: r.task }
  })
  return {
    backgroundColor: 'transparent',
    grid: { left: 30, right: 40, top: 16, bottom: 56, containLabel: true },
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const t = p.data?.task
        if (!t) return ''
        return `<b>${t.id}</b> ${t.title}<br/>${t.status} · ${t.owner || 'unassigned'} · ${t.priority || '-'}<br/>`
          + `${t.start || '?'} → ${t.due || '?'}${t.estimate ? ` (${t.estimate}d estimate)` : ''}`
          + `${t.milestone ? `<br/>${t.milestone}` : ''}`
      },
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
      data: rows.value.map((r) => r.label),
      axisLabel: { width: 470, overflow: 'truncate', fontSize: 11.5, fontFamily: 'ui-monospace, monospace' },
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
  if (p.data?.task) { selected.value = p.data.task; drawer.value = true }
}
const undated = computed(() => board.tasks.filter((t) => !t.start && !t.due && matches(t)))
</script>

<template>
  <el-card shadow="never" class="aim-sticky-head">
    <template #header>
      <div class="aim-filterbar">
        <span>timeline — {{ rows.length }} of {{ allDated.length }} dated item(s), {{ span.lo }} → {{ span.hi }}</span>
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
    <template #header>{{ undated.length }} item(s) with no dates, so no bar: they are work with no promise attached</template>
    <el-tag v-for="t in undated" :key="t.id" size="small" effect="plain" style="margin:2px" :type="STATUS_TYPE[t.status] || 'info'">
      {{ t.id }}
    </el-tag>
  </el-card>

  <TaskDecisionDrawer v-model="drawer" :task="selected" />
</template>
