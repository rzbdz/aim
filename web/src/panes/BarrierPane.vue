<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { PHASES, phaseLabel } from '../concepts'
import PhaseChip from '../components/PhaseChip.vue'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  channel: '', q: '', agent: '', refusalClass: '', phase: '',
})
const channels = computed(() => board.doc?.channels || [])
const current = computed(() =>
  channels.value.find((c) => c.id === (filters.channel || channels.value[0]?.id)) || {})
const chainRows = computed(() => Object.entries(current.value.chain || {})
  .map(([file, s]) => ({ file, ...s })))
const refusalRows = computed(() => (current.value.refusals || []).filter((row) => {
  if (filters.q) {
    const needle = filters.q.toLowerCase()
    if (!`${row.agent} ${row.action} ${row.reason}`.toLowerCase().includes(needle)) return false
  }
  if (filters.agent && row.agent !== filters.agent) return false
  if (filters.refusalClass && row.class !== filters.refusalClass) return false
  if (filters.phase && row.phase !== filters.phase) return false
  return true
}))
const refusalAgents = computed(() => [...new Set((current.value.refusals || [])
  .map((row) => row.agent).filter(Boolean))].sort())
</script>

<template>
  <el-tabs v-model="filters.channel" v-if="channels.length">
    <el-tab-pane v-for="ch in channels" :key="ch.id" :name="ch.id"
                   :label="`#${ch.id} — ${phaseLabel(ch.phase)}`">
      <el-descriptions :column="3" border size="small" style="margin-bottom:14px">
        <el-descriptions-item label="topic" :span="2">{{ ch.topic }}</el-descriptions-item>
        <el-descriptions-item label="leader">{{ ch.leader }}</el-descriptions-item>
        <el-descriptions-item label="phase">
          <PhaseChip :phase="ch.phase" effect="dark" link /> round {{ ch.round }}
        </el-descriptions-item>
        <el-descriptions-item label="participants">{{ (ch.participants || []).join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="work items in the store">{{ ch.tasks_recorded }}</el-descriptions-item>
        <el-descriptions-item label="refusals recorded">{{ (ch.refusals || []).length }}</el-descriptions-item>
        <el-descriptions-item label="concessions">{{ ch.concessions }}</el-descriptions-item>
      </el-descriptions>

      <el-card shadow="never" style="margin-bottom:14px">
        <template #header>the chain — every file the record is made of</template>
        <el-table :data="chainRows" size="small">
          <el-table-column prop="file" label="file" width="200" />
          <el-table-column label="state" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="row.state === 'OK' ? 'success' : row.state === 'EMPTY' ? 'info' : 'danger'" effect="dark">{{ row.state }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="records" label="records" width="110" />
          <el-table-column prop="why" label="why" min-width="240" />
        </el-table>
        <p class="aim-dim" style="font-size:12px">
          A hash chain is not a signature: it proves the file was not edited without also editing every
          later line, and it says nothing about who wrote the first one.
        </p>
        <el-alert v-if="ch.tasks_unknown_events" type="warning" :closable="false" show-icon
                  style="margin-top:8px" title="the store holds events the fold could not place">
          {{ ch.tasks_unknown_events }} event(s) name a task whose creation is not in this store. They are not
          on the board: a `moved` for a card that was never created is either a foreign writer or a truncated
          file, and either way the board would be quietly wrong if this number were not here.
        </el-alert>
      </el-card>

      <el-card shadow="never" style="margin-bottom:14px">
        <template #header>seals — a digest each participant committed to before reading the peer's</template>
        <el-table :data="ch.sealed" size="small">
          <el-table-column prop="agent" label="agent" width="180" />
          <el-table-column label="sealed" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.sealed ? 'success' : 'warning'" effect="dark">{{ row.sealed ? 'yes' : 'not yet' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="claims_count" label="claims" width="90" />
          <el-table-column prop="ts" label="at" width="200" />
          <el-table-column label="digest" min-width="200">
            <template #default="{ row }"><span class="aim-mono aim-dim">{{ (row.digest || '').slice(0, 24) }}…</span></template>
          </el-table-column>
          <el-table-column label="claims" min-width="380">
            <template #default="{ row }">
              <el-tag v-if="row.withheld" type="info" size="small" effect="plain">withheld while the channel is sealed</el-tag>
              <div v-for="c in row.claims || []" :key="c.id" style="font-size:12px;margin-top:4px">
                <b>{{ c.id }}</b> {{ c.claim }}
                <div class="aim-dim">confidence {{ c.confidence }} · would change my mind: {{ c.kill_if }}</div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" style="margin-bottom:14px">
        <template #header>
          <div class="aim-filterbar">
            <span>refusals — {{ refusalRows.length }} of {{ (ch.refusals || []).length }} record(s)</span>
            <el-input v-model="filters.q" placeholder="search action or reason" clearable />
            <el-select v-model="filters.agent" placeholder="agent" clearable>
              <el-option v-for="agent in refusalAgents" :key="agent" :value="agent" :label="agent" />
            </el-select>
            <el-select v-model="filters.refusalClass" placeholder="class" clearable>
              <el-option value="barrier" label="barrier" />
              <el-option value="form" label="form" />
            </el-select>
            <!-- The list is the dictionary's, not a copy: a filter that offers a
                 phase the tool cannot reach is a filter that can only return nothing. -->
            <el-select v-model="filters.phase" placeholder="phase" clearable>
              <el-option v-for="phase in PHASES" :key="phase.key" :value="phase.key"
                         :label="`${phase.label} (${phase.key})`" />
            </el-select>
            <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
          </div>
        </template>
        <el-table :data="refusalRows" size="small">
          <el-table-column prop="ts" label="at" width="200" />
          <el-table-column prop="agent" label="agent" width="160" />
          <el-table-column prop="action" label="attempted" min-width="240" />
          <el-table-column prop="class" label="class" width="110">
            <template #default="{ row }"><el-tag size="small" type="danger" effect="plain">{{ row.class }}</el-tag></template>
          </el-table-column>
          <el-table-column label="phase" width="150">
            <template #default="{ row }">
              <el-tooltip :content="row.phase" placement="top" :show-after="200">
                <span>{{ phaseLabel(row.phase) }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="reason" min-width="320" />
        </el-table>
        <el-empty v-if="!refusalRows.length" description="no refusal matches these filters" />
      </el-card>

      <el-card shadow="never">
        <template #header>phase history — only the leader moves it</template>
        <el-timeline>
          <el-timeline-item v-for="(h, i) in ch.history" :key="i" :timestamp="h.at" placement="top">
            <PhaseChip :phase="h.phase" effect="dark" link />
            <span class="aim-dim"> by {{ h.by }}{{ h.note ? ` — ${h.note}` : '' }}</span>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-tab-pane>
  </el-tabs>
  <el-empty v-else description="no channel to audit" />
</template>
