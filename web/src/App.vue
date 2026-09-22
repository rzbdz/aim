<script setup>
import { computed, inject } from 'vue'
import { useRoute } from 'vue-router'
import { useBoard } from './stores/board'
import OwnerAvatar from './components/OwnerAvatar.vue'

const ctx = inject('ctx')
const board = useBoard()
const route = useRoute()
const views = ctx.views
const current = computed(() => views.find((v) => v.key === route.meta.view))
const phaseType = computed(() => (board.phase.includes('SEALED') || board.phase === 'COMMIT' ? 'warning'
  : board.phase === '-' ? 'info' : 'success'))
const stamp = computed(() => (board.doc?.generated_at || '').replace('T', ' ').slice(0, 19))
const counts = computed(() => {
  const open = board.tasks.filter((t) => !board.terminal.includes(t.status)).length
  return { open, late: board.overdue.length, blocked: board.tasks.filter((t) => t.status === 'blocked').length }
})
const navGroups = computed(() => {
  const byKey = new Map(views.map((view) => [view.key, view]))
  return [
    { title: 'Work · 工作', keys: ['overview', 'kanban', 'gantt', 'items'] },
    { title: 'Conversation · 会话', keys: ['chat'] },
    { title: 'Insight · 报表', keys: ['reports'] },
    { title: 'Governance · 治理', keys: ['barrier', 'plan'] },
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
            <span>{{ v.titleZh || v.title }}</span>
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
        <el-tag :type="phaseType" effect="dark" size="small" round>phase {{ board.phase }}</el-tag>
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
        <el-alert v-if="board.stale" type="warning" :closable="false" show-icon style="margin-bottom:14px">
          <template #title>
            the record has moved since this page was drawn
            <el-button size="small" type="warning" style="margin-left:8px" @click="board.load()">refresh</el-button>
          </template>
        </el-alert>
        <el-alert v-if="board.error" type="error" show-icon :closable="false" style="margin-bottom:14px"
                  :title="`the board could not be read: ${board.error}`" />
        <div class="aim-page">
          <h2>{{ current?.titleZh || current?.title }}</h2>
          <span class="aim-sub">{{ current?.hint }}</span>
        </div>
        <el-skeleton v-if="!board.doc && board.loading" :rows="8" animated />
        <router-view v-else />
      </el-main>
    </el-container>
  </el-container>
</template>
