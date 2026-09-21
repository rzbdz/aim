<script setup>
import { computed, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import { useBoard } from '../stores/board'
import { MAIL_STATE_TYPE } from '../theme'

/**
 * What was actually said, and only what this viewer may read.
 *
 * `html: false` is not a default worth changing: message bodies are text other
 * agents wrote, and rendering them as HTML in the leader's browser would make the
 * fabric an injection channel. Markdown is a formatting language, not permission
 * to run code.
 */
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const render = (body) => md.render(body || '')
const board = useBoard()
const picked = ref('')
const q = ref('')

const threads = computed(() => {
  const out = []
  for (const ch of board.conversation.channels) {
    out.push({
      key: `ch:${ch.id}`, group: 'channel', label: `#${ch.id}`,
      sub: `${ch.messages.length} message(s) · ${ch.gated ? 'gated' : 'open'}`,
      note: ch.rule,
      msgs: ch.messages.map((m) => ({ by: m.from, to: `#${ch.id}`, ts: m.ts, body: m.body,
        chips: [m.kind && `kind ${m.kind}`, m.responds_to && `responds-to ${m.responds_to}`].filter(Boolean) })),
    })
  }
  for (const r of board.conversation.rooms) {
    out.push({
      key: `room:${r.channel}:${r.id}`, group: 'room', label: `#${r.channel} / #${r.id}`,
      sub: `${r.messages.length} message(s) · ${r.visibility}`,
      note: 'a room inherits the parent channel gate; draft by default, publishing is deliberate',
      msgs: r.messages.map((m) => ({ by: m.from, to: `#${r.id}`, ts: m.ts, body: m.body,
        chips: (m.mentions || []).map((x) => `@${x}`) })),
    })
  }
  const byPair = new Map()
  for (const m of board.conversation.mail) {
    const key = [m.from, m.to].sort().join(' ⇄ ')
    if (!byPair.has(key)) byPair.set(key, [])
    byPair.get(key).push(m)
  }
  for (const [key, msgs] of [...byPair].sort()) {
    out.push({
      key: `dm:${key}`, group: 'direct', label: key,
      sub: `${msgs.length} message(s)`,
      note: 'a direct message is a durable record with a receipt, not a chat window',
      msgs: msgs.sort((a, b) => (a.ts < b.ts ? -1 : 1)).map((m) => ({
        by: m.from, to: m.to, ts: m.ts, body: m.body, subject: m.subject,
        chips: [m.state, m.ack_required && 'receipt demanded', `${m.bytes} bytes`].filter(Boolean),
        state: m.state,
      })),
    })
  }
  return out
})
const groups = computed(() => {
  const g = {}
  for (const t of threads.value) (g[t.group] ||= []).push(t)
  return g
})
const current = computed(() => threads.value.find((t) => t.key === picked.value) || threads.value[0])
const messages = computed(() => {
  const msgs = current.value?.msgs || []
  if (!q.value) return msgs
  const needle = q.value.toLowerCase()
  return msgs.filter((m) => `${m.by} ${m.to} ${m.body}`.toLowerCase().includes(needle))
})
const dayOf = (ts) => (ts || '').slice(0, 10)
const replyCommand = computed(() => current.value?.group === 'direct'
  ? `aim push --as ${board.viewer} --to ${current.value.label.split(' ⇄ ').find((x) => x !== board.viewer) || 'peer'} --subject "..." --body-file <file>`
  : `aim say --as ${board.viewer} --channel ${current.value?.key.split(':')[1] || 'hello'} --body "..."`)
</script>

<template>
  <el-alert v-if="board.conversation.withheld" type="info" show-icon :closable="false" style="margin-bottom:12px"
            :title="`${board.conversation.withheld} message(s) are withheld from this view`" />
  <el-row :gutter="14">
    <el-col :span="7">
      <el-card shadow="never">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px">
            <span>threads ({{ threads.length }})</span>
            <el-button size="small" text @click="board.load()"><el-icon><Refresh /></el-icon></el-button>
          </div>
        </template>
        <el-scrollbar class="aim-scroll">
          <template v-for="(list, group) in groups" :key="group">
            <div class="aim-dim" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:6px 0 4px">{{ group }}</div>
            <div v-for="t in list" :key="t.key"
                 :style="{ padding: '7px 9px', borderRadius: '8px', cursor: 'pointer',
                           background: t.key === current?.key ? 'var(--el-fill-color)' : 'transparent' }"
                 @click="picked = t.key">
              <div style="font-size:12.5px">{{ t.label }}</div>
              <div class="aim-dim" style="font-size:11px">{{ t.sub }}</div>
            </div>
          </template>
          <el-empty v-if="!threads.length" description="nothing has been said on the record yet" />
        </el-scrollbar>
      </el-card>
    </el-col>

    <el-col :span="17">
      <el-card shadow="never">
        <template #header>
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
            <strong>{{ current?.label }}</strong>
            <el-tag v-if="current?.group === 'channel'" size="small" effect="plain" type="warning">{{ current?.note }}</el-tag>
            <span class="grow" style="flex:1" />
            <el-input v-model="q" size="small" placeholder="search in this thread" style="width:200px" clearable />
          </div>
        </template>
        <el-scrollbar class="aim-scroll">
          <div v-if="current?.group !== 'channel'" class="aim-dim" style="font-size:12px;margin-bottom:8px">{{ current?.note }}</div>
          <template v-for="(m, i) in messages" :key="i">
            <div v-if="i === 0 || dayOf(m.ts) !== dayOf(messages[i - 1].ts)" class="aim-daysep">{{ dayOf(m.ts) }}</div>
            <div class="aim-msg">
              <header>
                <strong>{{ m.by }}</strong>
                <el-icon v-if="m.to"><Right /></el-icon><strong v-if="m.to">{{ m.to }}</strong>
                <span class="aim-dim">{{ (m.ts || '').slice(11, 19) }}</span>
                <el-tag v-for="c in (m.chips || []).filter(Boolean)" :key="c" size="small" effect="plain"
                        :type="MAIL_STATE_TYPE[c] || 'info'">{{ c }}</el-tag>
              </header>
              <div v-if="m.subject" class="aim-dim" style="font-size:12.5px;margin-bottom:4px">{{ m.subject }}</div>
              <div class="body" v-html="render(m.body)" />
            </div>
          </template>
          <el-empty v-if="!messages.length" description="this thread is empty" />
        </el-scrollbar>
        <el-divider />
        <div class="aim-dim" style="font-size:12px">
          This page reads. It does not write: a chat box that writes into the record would be a second
          implementation of the write discipline. The command that would say this is
          <code class="aim-mono">{{ replyCommand }}</code>
          <el-button size="small" text @click="navigator.clipboard?.writeText(replyCommand)">
            <el-icon><DocumentCopy /></el-icon> copy
          </el-button>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>
