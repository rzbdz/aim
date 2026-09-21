<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'
import { MAIL_STATE_TYPE } from '../theme'

const board = useBoard()
const tab = ref('')
const channels = computed(() => board.doc?.channels || [])
const current = computed(() => channels.value.find((c) => c.id === (tab.value || channels.value[0]?.id)) || {})
const chainRows = computed(() => Object.entries(current.value.chain || {})
  .map(([file, s]) => ({ file, ...s })))
</script>

<template>
  <el-tabs v-model="tab" v-if="channels.length">
    <el-tab-pane v-for="ch in channels" :key="ch.id" :name="ch.id" :label="`#${ch.id} — ${ch.phase}`">
      <el-descriptions :column="3" border size="small" style="margin-bottom:14px">
        <el-descriptions-item label="topic" :span="2">{{ ch.topic }}</el-descriptions-item>
        <el-descriptions-item label="leader">{{ ch.leader }}</el-descriptions-item>
        <el-descriptions-item label="phase">
          <el-tag type="warning" effect="dark">{{ ch.phase }}</el-tag> round {{ ch.round }}
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
        <template #header>refusals — intent, not just outcome</template>
        <el-table :data="ch.refusals" size="small">
          <el-table-column prop="ts" label="at" width="200" />
          <el-table-column prop="agent" label="agent" width="160" />
          <el-table-column prop="action" label="attempted" min-width="240" />
          <el-table-column prop="class" label="class" width="110">
            <template #default="{ row }"><el-tag size="small" type="danger" effect="plain">{{ row.class }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="phase" label="phase" width="150" />
          <el-table-column prop="reason" label="reason" min-width="320" />
        </el-table>
        <el-empty v-if="!(ch.refusals || []).length" description="no refusals recorded on this channel" />
      </el-card>

      <el-card shadow="never">
        <template #header>phase history — only the leader moves it</template>
        <el-timeline>
          <el-timeline-item v-for="(h, i) in ch.history" :key="i" :timestamp="h.at" placement="top">
            <el-tag size="small" effect="dark" type="warning">{{ h.phase }}</el-tag>
            <span class="aim-dim"> by {{ h.by }}{{ h.note ? ` — ${h.note}` : '' }}</span>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-tab-pane>
  </el-tabs>
  <el-empty v-else description="no channel to audit" />
</template>
