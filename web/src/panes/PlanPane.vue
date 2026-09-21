<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'
import { STATUS_TYPE } from '../theme'

const board = useBoard()
const r = computed(() => board.register || {})
const milestones = computed(() => Object.values(board.milestones).map((m) => {
  const all = board.tasks.filter((t) => t.milestone === m.id)
  const done = all.filter((t) => board.terminal.includes(t.status)).length
  return { ...m, done, total: all.length, pct: all.length ? Math.round(100 * done / all.length) : 0 }
}))
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
    <template #header>milestones ({{ milestones.length }})</template>
    <el-table :data="milestones" size="small">
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
      <template #header>risks ({{ (r.risks || []).length }})</template>
      <el-table :data="r.risks || []" size="small">
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
      <template #header>decisions ({{ (r.decisions || []).length }})</template>
      <el-collapse>
        <el-collapse-item v-for="d in r.decisions || []" :key="d.id" :name="d.id">
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
    <template #header>who does what</template>
    <el-table :data="r.raci || []" size="small">
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
