<script setup>
import { computed, inject } from 'vue'
import { useRoute } from 'vue-router'
import { useBoard } from './stores/board'
import { phaseConcept } from './concepts'
import OwnerAvatar from './components/OwnerAvatar.vue'
import PhaseChip from './components/PhaseChip.vue'

const ctx = inject('ctx')
const board = useBoard()
const route = useRoute()
const views = ctx.views
const current = computed(() => views.find((v) => v.key === route.meta.view))
/**
 * The header says the phase in English and in full sentences, because it is the
 * one line that tells the leader what they may do next. The protocol value is in
 * the tooltip and one link away on Help & concepts; it is not the label.
 */
const phase = computed(() => phaseConcept(board.phase))
const phaseType = computed(() => (['SEALED_DIVERGENT', 'COMMIT', 'SYNTHESIS'].includes(board.phase) ? 'warning'
  : board.phase === '-' ? 'info' : 'success'))
const stamp = computed(() => (board.doc?.generated_at || '').replace('T', ' ').slice(0, 19))
const counts = computed(() => {
  const open = board.tasks.filter((t) => !board.terminal.includes(t.status)).length
  return { open, late: board.overdue.length, blocked: board.tasks.filter((t) => t.status === 'blocked').length }
})
const navGroups = computed(() => {
  const byKey = new Map(views.map((view) => [view.key, view]))
  return [
    { title: 'Work', keys: ['attention', 'kanban', 'gantt', 'items'] },
    { title: 'Conversation', keys: ['chat'] },
    { title: 'Insight', keys: ['reports'] },
    { title: 'Governance', keys: ['barrier', 'plan'] },
    // Concepts last, and in the nav rather than hidden behind a "?": the reader
    // who needs it is the one who does not yet know what to look for.
    { title: 'Reference', keys: ['help'] },
  ].map((group) => ({
    title: group.title,
    views: group.keys.map((key) => byKey.get(key)).filter(Boolean),
  })).filter((group) => group.views.length)
})
</script>

<template>
  <el-container class="aim-shell">
    <el-aside width="216px" class="aim-aside">
      <div class="aim-brand">
        <h1><span class="aim-mark">aim</span> board</h1>
        <div class="aim-sub">
          <div>{{ board.doc?.root?.split('/').pop() || '…' }} · {{ board.doc?.as_of }}</div>
          <div>{{ counts.open }} open · {{ counts.late }} late · {{ counts.blocked }} blocked</div>
        </div>
      </div>
      <el-menu :default-active="route.path" router>
        <el-menu-item-group v-for="group in navGroups" :key="group.title" :title="group.title">
          <el-menu-item v-for="v in group.views" :key="v.key" :index="`/${v.key}`">
            <el-icon><component :is="v.icon || 'Grid'" /></el-icon>
            <span>{{ v.title }}</span>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>
      <div class="aim-links aim-dim">
        <div style="margin-bottom:6px">for a foreign tool</div>
        <el-button-group>
          <el-button size="small" tag="a" href="/api/state">json</el-button>
          <el-button size="small" tag="a" href="/board.csv">csv</el-button>
          <el-button size="small" tag="a" href="/board.ics">ical</el-button>
        </el-button-group>
      </div>
    </el-aside>

    <el-container>
      <el-header height="auto" class="aim-header">
        <!-- The chip is the same component the audit page uses: one place knows
             what a phase is called, and one place knows that a tooltip around a
             link must not eat the key that activates it. -->
        <PhaseChip :phase="board.phase" :type="phaseType" effect="dark" round link />
        <span class="aim-dim aim-header-phase" style="font-size:11.5px">{{ phase.summary }}</span>
        <span v-if="board.withheld" class="aim-dim" style="font-size:11.5px">
          {{ board.withheld }} withheld from this view
        </span>
        <span style="flex:1" />
        <span class="aim-dim" style="font-size:11px">as of {{ stamp }}</span>
        <OwnerAvatar :id="board.viewer" :size="20" />
        <el-select :model-value="board.viewer" size="small" style="width:190px" @change="board.setViewer"
                   placeholder="whose view">
          <el-option v-for="(a, id) in board.agents" :key="id" :value="id" :label="`${id} · ${a.kind}`" />
        </el-select>
        <el-button size="small" :loading="board.loading" @click="board.load()">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-header>

      <el-main :class="['aim-main', { 'aim-main-conversation': current?.key === 'chat' }]">
        <!--
          Not a warning. A refresh is not an error, and the board updates itself;
          this line exists only for the case where it deliberately did not, so the
          reader is told what is waiting and given one quiet way to take it now.
        -->
        <div v-if="board.deferred" class="aim-deferred">
          <span class="aim-dim">
            newer activity on the record — held back because {{ board.deferredReason }}.
          </span>
          <el-button size="small" text type="primary" @click="board.update({ force: true })">
            update now
          </el-button>
        </div>
        <el-alert v-if="board.error" type="error" show-icon :closable="false" style="margin-bottom:14px"
                  :title="`the board could not be read: ${board.error}`" />
        <div class="aim-page">
          <h2>{{ current?.title }}</h2>
          <span class="aim-sub">{{ current?.hint }}</span>
        </div>
        <el-skeleton v-if="!board.doc && board.loading" :rows="8" animated />
        <router-view v-else />
      </el-main>
    </el-container>
  </el-container>
</template>
