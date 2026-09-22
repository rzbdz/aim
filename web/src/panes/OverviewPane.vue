<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'
import { STATUS_TYPE, PRIORITY_TYPE, isOverdue } from '../theme'

const board = useBoard()
const stats = computed(() => {
  const t = board.tasks
  const done = t.filter((x) => board.terminal.includes(x.status)).length
  return {
    total: t.length, done, open: t.length - done,
    doing: t.filter((x) => x.status === 'doing').length,
    blocked: t.filter((x) => x.status === 'blocked').length,
    overdue: board.overdue.length,
    recorded: board.recorded.length, seedOnly: board.seedOnly.length,
    messages: board.conversationRows.length,
  }
})
const nextDue = computed(() => board.tasks
  .filter((t) => t.due && !board.terminal.includes(t.status))
  .sort((a, b) => (a.due < b.due ? -1 : 1)).slice(0, 8))
const msRows = computed(() => Object.values(board.milestones).map((m) => {
  const all = board.tasks.filter((t) => t.milestone === m.id)
  const done = all.filter((t) => board.terminal.includes(t.status)).length
  return { ...m, done, total: all.length, pct: all.length ? Math.round(100 * done / all.length) : 0 }
}))
const recent = computed(() => board.conversationRows.slice(-6).reverse())
const preview = (message) => message.subject || message.body || '(nothing yet)'
</script>

<template>
  <el-alert v-if="board.withheld" type="info" :closable="false" show-icon style="margin-bottom:12px"
            title="the barrier is in force: peer drafts and peer seals are absent from this view, not hidden" />
  <el-alert v-if="board.unacked.length" type="warning" :closable="false" show-icon style="margin-bottom:12px">
    <template #title>{{ board.unacked.length }} message(s) demand a receipt that has not arrived</template>
    <el-table :data="board.unacked" size="small" style="margin-top:8px">
      <el-table-column prop="msg_id" label="message" width="330" />
      <el-table-column prop="from" label="from" width="140" />
      <el-table-column prop="to" label="to" width="140" />
      <el-table-column prop="bytes" label="bytes" width="90" />
    </el-table>
  </el-alert>

  <div class="aim-grid" style="margin-bottom:14px">
    <el-card v-for="s in [
      { label: 'work items', v: stats.total, sub: `${stats.recorded} recorded · ${stats.seedOnly} plan seed` },
      { label: 'done', v: stats.done, sub: `${stats.open} open` },
      { label: 'in flight', v: stats.doing, sub: `${stats.blocked} blocked` },
      { label: 'overdue', v: stats.overdue, sub: 'past the due date and not terminal' },
      { label: 'messages', v: stats.messages, sub: `${board.unacked.length} awaiting a receipt` },
      { label: 'median cycle', v: board.report.median_cycle ?? '—', sub: `${board.report.with_history} items have history` },
    ]" :key="s.label" shadow="never">
      <div class="aim-stat">
        <el-statistic :title="s.label" :value="s.v" />
        <div class="aim-dim" style="font-size:11.5px;margin-top:6px">{{ s.sub }}</div>
      </div>
    </el-card>
  </div>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>milestones — a fold over the record, not a file anybody edits</template>
    <el-table :data="msRows" size="small">
      <el-table-column prop="id" label="id" width="70" />
      <el-table-column prop="name" label="name" min-width="180" />
      <el-table-column prop="due" label="due" width="110" />
      <el-table-column label="progress" width="220">
        <template #default="{ row }">
          <el-progress :percentage="row.pct" :stroke-width="10" />
          <span class="aim-dim" style="font-size:11px">{{ row.done }}/{{ row.total }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="accept" label="acceptance" min-width="300" />
    </el-table>
  </el-card>

  <div class="aim-grid">
    <el-card shadow="never">
      <template #header>next due</template>
      <el-table :data="nextDue" size="small" :show-header="false">
        <el-table-column width="86">
          <template #default="{ row }"><span class="aim-mono">{{ row.id }}</span></template>
        </el-table-column>
        <el-table-column>
          <template #default="{ row }">
            <div>{{ row.title }}</div>
            <div class="aim-dim" style="font-size:11.5px">
              {{ row.owner || 'unassigned' }} ·
              <el-tag size="small" :type="PRIORITY_TYPE[row.priority] || 'info'" effect="plain">{{ row.priority }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="isOverdue(row.due, row.status, board.terminal) ? 'danger' : 'info'" effect="plain">{{ row.due }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>latest on the record</template>
      <div v-for="m in recent" :key="`${m.shape}:${m.msg_id || m.hash || m.ts}`" class="aim-msg">
        <header>
          <strong>{{ m.from }}</strong><el-icon><Right /></el-icon><strong>{{ m.scope }}</strong>
          <span class="aim-dim">{{ m.ts }}</span>
          <el-tag size="small" effect="plain" :type="m.shape === 'direct' ? 'info' : 'primary'">{{ m.shape }}</el-tag>
          <el-tag v-if="m.state" size="small" :type="m.state === 'acked' ? 'success' : m.state === 'claimed' ? 'warning' : 'info'" effect="plain">{{ m.state }}</el-tag>
          <el-tag v-if="m.ack_required" size="small" type="danger" effect="plain">receipt demanded</el-tag>
        </header>
        <div class="aim-dim" style="font-size:12.5px">{{ preview(m) }}</div>
      </div>
    </el-card>
  </div>

  <el-card v-if="board.drift.length" shadow="never" style="margin-top:14px">
    <template #header>plan versus store — {{ board.drift.length }} disagreement(s)</template>
    <p class="aim-dim" style="font-size:12.5px">
      The plan file is a picture; the store is the evidence. Where they disagree, the store wins and
      this table is how you find out that they do.
    </p>
    <el-table :data="board.drift.slice(0, 40)" size="small">
      <el-table-column prop="id" label="id" width="90" />
      <el-table-column prop="field" label="field" width="120" />
      <el-table-column label="plan" min-width="160"><template #default="{ row }">{{ row.plan ?? '—' }}</template></el-table-column>
      <el-table-column label="store" min-width="160"><template #default="{ row }">{{ row.store ?? '(nothing recorded)' }}</template></el-table-column>
    </el-table>
  </el-card>
</template>
