<script setup>
import { computed, ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ElMessageBox } from 'element-plus'
import { useBoard } from '../stores/board'
import { isOverdue } from '../theme'
import StatusTag from '../components/StatusTag.vue'
import OwnerAvatar from '../components/OwnerAvatar.vue'

const board = useBoard()
const cols = ref({})
const owner = ref('')
const milestone = ref('')
const compact = ref(false)

const visible = (t) => (!owner.value || t.owner === owner.value) && (!milestone.value || t.milestone === milestone.value)
function sync() {
  const next = {}
  for (const st of board.statuses) next[st] = (board.byStatus[st] || []).filter(visible)
  cols.value = next
}
watch(() => [board.doc, owner.value, milestone.value], sync, { immediate: true })

/**
 * The board is read-only, and dragging is how you find that out.
 *
 * A drag is a real intention, so it is not swallowed: it becomes the exact
 * command that would carry it out. The alternative - a drag that writes - is the
 * second implementation of the write discipline (design/05 D6); the alternative -
 * a drag that silently snaps back - teaches the reader that the board is broken.
 */
async function onMoved(evt) {
  const id = evt.item?.dataset?.id
  const to = evt.to?.dataset?.status
  const from = evt.from?.dataset?.status
  sync()
  if (!id || !to || to === from) return
  const command = `aim task move --as ${board.viewer} --id ${id} --to ${to}`
  await ElMessageBox.alert(command, `${id} — the dashboard does not write`, {
    confirmButtonText: 'copy the command', showCancelButton: true, cancelButtonText: 'close',
    customClass: 'aim-mono',
  }).then(() => navigator.clipboard?.writeText(command)).catch(() => {})
}
const estimate = (t) => (t.estimate ? `${t.estimate}d` : '')
</script>

<template>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px">
    <el-select v-model="owner" size="small" placeholder="any owner" clearable style="width:170px">
      <el-option v-for="o in board.owners" :key="o" :value="o" :label="o" />
    </el-select>
    <el-select v-model="milestone" size="small" placeholder="any milestone" clearable style="width:180px">
      <el-option v-for="(m, id) in board.milestones" :key="id" :value="id" :label="`${id} ${m.name || ''}`" />
    </el-select>
    <el-checkbox v-model="compact" size="small">compact</el-checkbox>
    <span style="flex:1" />
    <span class="aim-dim" style="font-size:11.5px">
      {{ board.withheld ? `${board.withheld} withheld · ` : '' }}drag shows the command, it does not write
    </span>
  </div>

  <div class="aim-board">
    <section v-for="st in board.statuses" :key="st" class="aim-col">
      <header>
        <StatusTag :status="st" />
        <span class="aim-count">{{ (cols[st] || []).length }}</span>
      </header>
      <VueDraggable v-model="cols[st]" :group="{ name: 'tasks' }" :data-status="st"
                    class="aim-colbody" :animation="140" @end="onMoved">
        <article v-for="t in cols[st]" :key="t.id" class="aim-card" :data-id="t.id">
          <div style="display:flex;align-items:baseline;gap:8px">
            <span class="aim-id">{{ t.id }}</span>
            <span style="flex:1" />
            <span v-if="estimate(t)" class="aim-id">{{ estimate(t) }}</span>
          </div>
          <span class="aim-title">{{ t.title }}</span>
          <template v-if="!compact">
            <div v-if="t.accept" class="aim-accept">
              <el-icon style="margin-top:2px"><Aim /></el-icon><span>{{ t.accept }}</span>
            </div>
          </template>
          <div class="aim-meta">
            <OwnerAvatar :id="t.owner" :size="18" />
            <span v-if="t.due" :class="{ 'aim-late': isOverdue(t.due, t.status, board.terminal) }">
              {{ t.due.slice(5) }}{{ isOverdue(t.due, t.status, board.terminal) ? ' late' : '' }}
            </span>
            <span v-if="t.milestone">{{ t.milestone }}</span>
            <template v-for="b in t.blocked_by || []" :key="b">
              <span class="aim-flag blocked"><el-icon><Lock /></el-icon>{{ b }}</span>
            </template>
            <span v-if="t.priority && t.priority !== 'medium'" class="aim-flag"
                  :style="{ color: t.priority === 'high' ? '#fca5a5' : 'inherit' }">
              <el-icon><Top v-if="t.priority === 'high'" /><Bottom v-else /></el-icon>{{ t.priority }}
            </span>
          </div>
          <div v-if="(t.tags || []).length || t.visibility === 'draft' || (t.provenance || '').includes('seed')"
               style="display:flex;gap:5px;flex-wrap:wrap;margin-top:8px">
            <span v-if="(t.provenance || '').includes('seed')" class="aim-chip seed">plan seed</span>
            <span v-if="t.visibility === 'draft'" class="aim-chip draft">draft</span>
            <span v-for="g in (t.tags || []).slice(0, 4)" :key="g" class="aim-chip">{{ g }}</span>
          </div>
        </article>
      </VueDraggable>
    </section>
  </div>
</template>
