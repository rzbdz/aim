<script setup>
import { computed, watch } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { PHASES, phaseLabel } from '../concepts'
import PhaseChip from '../components/PhaseChip.vue'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  channel: '', q: '', agent: '', refusalClass: '', phase: '',
})
const channels = computed(() => board.doc?.channels || [])
/**
 * The channel being drawn and the channel the URL names are the same channel.
 *
 * They were not, and the page said so out loud: with no `?channel=` the detail
 * panel fell back to the first channel, while every tab rendered unselected --
 * five channels, zero `is-active`, and `#barrier-v0`'s topic, phase and
 * participants on screen underneath. A tab strip that says "nothing is selected"
 * above a panel showing something is the reader being told two things at once,
 * and the one they will believe is the wrong one.
 *
 * So the fallback *is* the selection: the id that is drawn is written to the URL,
 * and the URL stays the source of truth for every other change.
 *
 * The strip is *bound*, not `v-model`ed. `v-model="shown"` was the second half of
 * this defect: `shown` is a computed, so the tab's `update:modelValue` assigned
 * to a readonly ref, the assignment was dropped, and in a production build Vue's
 * dev-time warning is stripped -- so `el-tabs` moved its own highlight and the
 * pane switched on screen while `filters.channel` and the URL did not move at
 * all. Measured: click `#hello` and `location.hash` still ended in
 * `channel=barrier-v0`, with the refusals table rendering nothing. The reader is
 * now the one who writes the selection, through the same `filters.channel` the
 * rest of the page reads.
 */
const shown = computed(() => filters.channel || channels.value[0]?.id || '')
const current = computed(() => channels.value.find((c) => c.id === shown.value) || {})
watch(shown, (id) => {
  if (id && filters.channel !== id) filters.channel = id
}, { immediate: true })

/**
 * The rows a refusal table draws, asked for a named channel rather than for "the
 * current one".
 *
 * The table is rendered inside `v-for="ch in channels"`, and it used to read the
 * filters against `current` -- the channel named by the URL. On load those are
 * the same channel, so the page looked right. After a tab click they are not, and
 * the sentence above the table printed a numerator from one channel over a
 * denominator from another: measured, "0 of 13 record(s)" over an empty table,
 * while 15 refusals sat one click away. A number and the list under it have to be
 * the same question asked once, so both are computed from the `ch` the table is
 * actually drawn in.
 */
function refusalsOf(channel) {
  return (channel?.refusals || []).filter((row) => {
    if (filters.q) {
      const needle = filters.q.toLowerCase()
      if (!`${row.agent} ${row.action} ${row.reason}`.toLowerCase().includes(needle)) return false
    }
    if (filters.agent && row.agent !== filters.agent) return false
    if (filters.refusalClass && row.class !== filters.refusalClass) return false
    if (filters.phase && row.phase !== filters.phase) return false
    return true
  })
}

function refusalAgentsOf(channel) {
  return [...new Set((channel?.refusals || []).map((row) => row.agent).filter(Boolean))].sort()
}
const chainRows = computed(() => Object.entries(current.value.chain || {})
  .map(([file, s]) => ({ file, ...s })))
</script>

<template>
  <el-tabs :model-value="shown" @update:model-value="(id) => { filters.channel = id }"
           v-if="channels.length">
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
            <span>refusals — {{ refusalsOf(ch).length }} of {{ (ch.refusals || []).length }} record(s)</span>
            <el-input v-model="filters.q" placeholder="search action or reason" clearable />
            <el-select v-model="filters.agent" placeholder="agent" clearable>
              <el-option v-for="agent in refusalAgentsOf(ch)" :key="agent" :value="agent" :label="agent" />
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
        <el-table :data="refusalsOf(ch)" size="small" class="aim-refusal-table">
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
        <el-empty v-if="!refusalsOf(ch).length" description="no refusal matches these filters" />
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
