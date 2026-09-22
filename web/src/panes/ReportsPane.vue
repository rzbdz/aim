<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { STATUS_TYPE } from '../theme'
import TaskLink from '../components/TaskLink.vue'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', blocker: '',
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
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { opacity: 0.18 } } },
    series: [
      { name: 'remaining', type: 'line', smooth: true, data: (r.series || []).map((x) => x.remaining), areaStyle: { opacity: 0.12 } },
      { name: 'done', type: 'line', smooth: true, data: (r.series || []).map((x) => x.done) },
    ],
  }
})
const burndownEmpty = computed(() => !(board.report.series || []).some((x) => x.done || x.remaining))
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
</script>

<template>
  <div class="aim-grid" style="margin-bottom:14px">
    <el-card shadow="never">
      <el-statistic title="median cycle time (days)" :value="board.report.median_cycle ?? 0" />
      <div class="aim-dim" style="font-size:11.5px">{{ board.report.with_history }} item(s) have move history</div>
    </el-card>
    <el-card shadow="never">
      <el-statistic title="recorded in the store" :value="board.report.recorded" />
      <div class="aim-dim" style="font-size:11.5px">{{ board.report.seed_only }} item(s) are plan seed only</div>
    </el-card>
    <el-card shadow="never">
      <el-statistic title="throughput (last 7 days)" :value="(board.report.throughput || []).length" />
      <div class="aim-dim" style="font-size:11.5px">closed items, from recorded events</div>
    </el-card>
  </div>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>burndown — remaining work per day, folded from the store</template>
    <el-alert v-if="burndownEmpty" type="info" :closable="false" show-icon style="margin-bottom:10px"
              title="flat at zero because nothing is recorded in the store yet: this chart is drawn from events, and a plan seed has none" />
    <VChart :option="option" autoresize style="height:320px" />
  </el-card>

  <el-card shadow="never">
    <template #header>
      <div class="aim-filterbar">
        <span>what is waiting on what — {{ blockedRows.length }} of {{ (board.report.blocked || []).length }} blocker row(s)</span>
        <el-input v-model="filters.q" placeholder="search blocked item" clearable />
        <el-select v-model="filters.owner" placeholder="owner" clearable>
          <el-option v-for="owner in board.owners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-select v-model="filters.status" placeholder="status" clearable>
          <el-option v-for="status in board.statuses" :key="status" :value="status" :label="status" />
        </el-select>
        <el-select v-model="filters.blocker" placeholder="waiting on" clearable>
          <el-option v-for="blocker in blockerOptions" :key="blocker" :value="blocker" :label="blocker" />
        </el-select>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
      </div>
    </template>
    <el-table :data="blockedRows" size="small">
      <el-table-column label="blocked item" width="130">
        <template #default="{ row }"><TaskLink :id="row.id" /></template>
      </el-table-column>
      <el-table-column prop="title" label="title" min-width="300" />
      <el-table-column prop="status" label="status" width="110">
        <template #default="{ row }"><el-tag size="small" :type="STATUS_TYPE[row.status] || 'info'" effect="plain">{{ row.status }}</el-tag></template>
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
    <p class="aim-dim" style="font-size:12px">
      A blocker is an edge in the graph, not a label on a card: it is only a blocker while the item it names
      is not done, which is why this table is computed rather than written down.
    </p>
  </el-card>
</template>
