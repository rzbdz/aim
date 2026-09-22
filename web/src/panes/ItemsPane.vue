<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { PRIORITY_TYPE, STATUS_TYPE, isOverdue } from '../theme'
import TaskDecisionDrawer from '../components/TaskDecisionDrawer.vue'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  q: '', owner: '', status: '', milestone: '', tag: '', onlyLate: false,
})
const selected = ref(null)
const drawer = ref(false)

const rows = computed(() => board.tasks.filter((t) => {
  const search = filters.q.toLowerCase()
  if (search && !`${t.id} ${t.title} ${t.accept || ''}`.toLowerCase().includes(search)) return false
  if (filters.owner && t.owner !== filters.owner) return false
  if (filters.status && t.status !== filters.status) return false
  if (filters.milestone && t.milestone !== filters.milestone) return false
  if (filters.tag && !(t.tags || []).includes(filters.tag)) return false
  if (filters.onlyLate && !isOverdue(t.due, t.status, board.terminal)) return false
  return true
}))
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="aim-filterbar">
        <el-input v-model="filters.q" placeholder="search id, title, acceptance" clearable>
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filters.owner" placeholder="owner" clearable>
          <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
        </el-select>
        <el-select v-model="filters.status" placeholder="status" clearable>
          <el-option v-for="s in board.statuses" :key="s" :value="s" :label="s" />
        </el-select>
        <el-select v-model="filters.milestone" placeholder="milestone" clearable>
          <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
        </el-select>
        <el-select v-model="filters.tag" placeholder="tag" clearable>
          <el-option v-for="t in board.tags" :key="t" :value="t" :label="t" />
        </el-select>
        <el-checkbox v-model="filters.onlyLate">overdue only</el-checkbox>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <span class="aim-filter-count">{{ rows.length }} of {{ board.tasks.length }}</span>
      </div>
    </template>

    <el-table :data="rows" size="small" @row-click="(r) => { selected = r; drawer = true }"
              :default-sort="{ prop: 'id' }" style="cursor:pointer">
      <el-table-column prop="id" label="id" width="86" sortable />
      <el-table-column label="action" width="86" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text :aria-label="`Inspect task ${row.id}`"
                     @click.stop="selected = row; drawer = true">inspect</el-button>
        </template>
      </el-table-column>
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

  <TaskDecisionDrawer v-model="drawer" :task="selected" />
</template>
