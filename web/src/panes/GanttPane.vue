<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE, color, days, today } from '../theme'

const board = useBoard()
const selected = ref(null)
const drawer = ref(false)
const milestone = ref('all')

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
const rows = computed(() => {
  const dated = allDated.value.filter((t) => milestone.value === 'all' || t.milestone === milestone.value)
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
          lineStyle: { color: '#f87171', type: 'dashed' },
          label: { formatter: 'today', color: '#f87171' },
        },
      },
    ],
  }
})
function onClick(p) {
  if (p.data?.task) { selected.value = p.data.task; drawer.value = true }
}
const undated = computed(() => board.tasks.filter((t) => !t.start && !t.due))
</script>

<template>
  <el-card shadow="never" class="aim-sticky-head">
    <template #header>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <span>timeline — {{ rows.length }} of {{ allDated.length }} dated item(s), {{ span.lo }} → {{ span.hi }}</span>
        <el-select v-model="milestone" size="small" style="width:150px">
          <el-option value="all" label="every milestone" />
          <el-option v-for="m in milestones" :key="m" :value="m" :label="m" />
        </el-select>
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

  <el-drawer v-model="drawer" :title="selected?.id" size="46%">
    <template v-if="selected">
      <h3 style="margin-top:0">{{ selected.title }}</h3>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="status"><el-tag :type="STATUS_TYPE[selected.status]" effect="dark">{{ selected.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="owner">{{ selected.owner || '—' }}</el-descriptions-item>
        <el-descriptions-item label="priority"><el-tag :type="PRIORITY_TYPE[selected.priority]" effect="plain">{{ selected.priority }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="estimate">{{ selected.estimate ?? '—' }} day(s)</el-descriptions-item>
        <el-descriptions-item label="start">{{ selected.start || '—' }}</el-descriptions-item>
        <el-descriptions-item label="due">{{ selected.due || '—' }}</el-descriptions-item>
        <el-descriptions-item label="milestone">{{ selected.milestone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="blocked by">{{ (selected.blocked_by || []).join(', ') || 'nothing' }}</el-descriptions-item>
        <el-descriptions-item label="acceptance" :span="2">{{ selected.accept || '—' }}</el-descriptions-item>
        <el-descriptions-item label="provenance" :span="2">{{ selected.provenance || '—' }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="(selected.comments || []).length" style="margin-top:14px">
        <h4>comments</h4>
        <div v-for="(c, i) in selected.comments" :key="i" class="aim-msg">
          <header><strong>{{ c.by }}</strong><span class="aim-dim">{{ c.ts }}</span></header>
          <div>{{ c.body }}</div>
        </div>
      </div>
    </template>
  </el-drawer>
</template>
