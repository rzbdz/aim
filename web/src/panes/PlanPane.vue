<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  q: '', progress: 'all', owner: '', riskOwner: '',
})
const r = computed(() => board.register || {})
const milestones = computed(() => Object.values(board.milestones).map((m) => {
  const all = board.tasks.filter((t) => t.milestone === m.id)
  const done = all.filter((t) => board.terminal.includes(t.status)).length
  return { ...m, done, total: all.length, pct: all.length ? Math.round(100 * done / all.length) : 0 }
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
const withoutDates = computed(() => board.tasks.filter((t) => !t.due).length)
</script>

<template>
  <el-alert type="info" :closable="false" show-icon style="margin-bottom:14px">
    <template #title>
      plan/*.json is the leader's plan and a <b>seed</b>. The store is the evidence: where the two disagree the
      store wins, and the {{ board.drift.length }} disagreement(s) are on the overview. {{ withoutDates }} item(s)
      have no due date, which in a plan is a sentence without a verb.
    </template>
  </el-alert>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>milestones ({{ visibleMilestones.length }} of {{ milestones.length }})</span>
        <el-input v-model="filters.q" placeholder="search milestones, risks, decisions" clearable />
        <el-select v-model="filters.progress" placeholder="progress">
          <el-option value="all" label="all progress" />
          <el-option value="open" label="open" />
          <el-option value="done" label="done" />
        </el-select>
        <el-select v-model="filters.owner" placeholder="work owner" clearable>
          <el-option v-for="owner in board.owners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-select v-model="filters.riskOwner" placeholder="risk owner" clearable>
          <el-option v-for="owner in riskOwners" :key="owner" :value="owner" :label="owner" />
        </el-select>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
      </div>
    </template>
    <el-table :data="visibleMilestones" size="small">
      <el-table-column prop="id" label="id" width="70" />
      <el-table-column prop="name" label="name" min-width="200" />
      <el-table-column prop="due" label="due" width="110" />
      <el-table-column label="progress" width="230">
        <template #default="{ row }">
          <el-progress :percentage="row.pct" :stroke-width="10" />
          <span class="aim-dim" style="font-size:11px">{{ row.done }}/{{ row.total }}</span>
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
