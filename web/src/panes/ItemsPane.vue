<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'

const board = useBoard()
const q = ref('')
const owner = ref('')
const status = ref('')
const milestone = ref('')
const tag = ref('')
const onlyLate = ref(false)
const selected = ref(null)
const drawer = ref(false)

const rows = computed(() => board.tasks.filter((t) => {
  if (q.value && !`${t.id} ${t.title} ${t.accept || ''}`.toLowerCase().includes(q.value.toLowerCase())) return false
  if (owner.value && t.owner !== owner.value) return false
  if (status.value && t.status !== status.value) return false
  if (milestone.value && t.milestone !== milestone.value) return false
  if (tag.value && !(t.tags || []).includes(tag.value)) return false
  if (onlyLate.value && !isOverdue(t.due, t.status, board.terminal)) return false
  return true
}))
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <el-input v-model="q" placeholder="search id, title, acceptance" style="width:260px" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="owner" placeholder="owner" clearable style="width:140px">
          <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
        </el-select>
        <el-select v-model="status" placeholder="status" clearable style="width:130px">
          <el-option v-for="s in board.statuses" :key="s" :value="s" :label="s" />
        </el-select>
        <el-select v-model="milestone" placeholder="milestone" clearable style="width:130px">
          <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
        </el-select>
        <el-select v-model="tag" placeholder="tag" clearable style="width:140px">
          <el-option v-for="t in board.tags" :key="t" :value="t" :label="t" />
        </el-select>
        <el-checkbox v-model="onlyLate">overdue only</el-checkbox>
        <span class="aim-dim">{{ rows.length }} of {{ board.tasks.length }}</span>
      </div>
    </template>

    <el-table :data="rows" size="small" @row-click="(r) => { selected = r; drawer = true }"
              :default-sort="{ prop: 'id' }" style="cursor:pointer">
      <el-table-column prop="id" label="id" width="86" sortable />
      <el-table-column prop="title" label="title" min-width="300" show-overflow-tooltip />
      <el-table-column prop="status" label="status" width="104" sortable>
        <template #default="{ row }"><el-tag size="small" :type="STATUS_TYPE[row.status] || 'info'" effect="dark">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="owner" label="owner" width="130" sortable />
      <el-table-column prop="priority" label="priority" width="96" sortable>
        <template #default="{ row }"><el-tag size="small" :type="PRIORITY_TYPE[row.priority] || 'info'" effect="plain">{{ row.priority }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="milestone" label="ms" width="70" sortable />
      <el-table-column prop="start" label="start" width="106" sortable />
      <el-table-column prop="due" label="due" width="118" sortable>
        <template #default="{ row }">
          <span :class="{ 'aim-late': isOverdue(row.due, row.status, board.terminal) }">
            {{ row.due || '—' }}<el-tag v-if="isOverdue(row.due, row.status, board.terminal)" size="small" type="danger" effect="plain" style="margin-left:4px">late</el-tag>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="estimate" label="est" width="66" sortable />
      <el-table-column label="blocked by" width="110">
        <template #default="{ row }">
          <el-tag v-for="b in row.blocked_by || []" :key="b" size="small" type="danger" effect="plain">{{ b }}</el-tag>
          <span v-if="!(row.blocked_by || []).length" class="aim-dim">—</span>
        </template>
      </el-table-column>
      <el-table-column label="tags" min-width="150">
        <template #default="{ row }">
          <el-tag v-for="t in row.tags || []" :key="t" size="small" effect="plain" type="info" style="margin-right:3px">{{ t }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawer" :title="selected?.id" size="46%">
    <template v-if="selected">
      <h3 style="margin-top:0">{{ selected.title }}</h3>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="acceptance">{{ selected.accept || '—' }}</el-descriptions-item>
        <el-descriptions-item label="notes">{{ selected.notes || '—' }}</el-descriptions-item>
        <el-descriptions-item label="provenance">{{ selected.provenance || '—' }}</el-descriptions-item>
        <el-descriptions-item label="events">{{ (selected.events || []).length }} recorded transition(s)</el-descriptions-item>
        <el-descriptions-item label="move history">
          <div v-for="(e, i) in selected.events || []" :key="i" class="aim-mono">
            {{ e.ts || e.at }} {{ e.by }} {{ e.event || e.kind }} {{ e.to ? `→ ${e.to}` : '' }} {{ e.reason || e.move_reason || '' }}
          </div>
          <span v-if="!(selected.events || []).length" class="aim-dim">nothing recorded: this is still a plan seed</span>
        </el-descriptions-item>
      </el-descriptions>
    </template>
  </el-drawer>
</template>
