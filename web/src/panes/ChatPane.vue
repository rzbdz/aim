<script setup>
import { computed, inject, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useBoard } from '../stores/board'
import OwnerAvatar from '../components/OwnerAvatar.vue'
import { MAIL_STATE_TYPE } from '../theme'

/**
 * Reading the conversation is the point of this pane, so the layout is a
 * bounded reader: the history owns one scroller, the composer owns the bottom,
 * and they are siblings rather than an input floating over a page. The first
 * version put a sticky composer inside the normal page flow, so it overlapped
 * exactly the long reports the leader needed to read.
 */
const ctx = inject('ctx')
const md = ctx.service('markdown')
const api = ctx.service('api')
const board = useBoard()

const picked = ref('')
const q = ref('')
const drafting = ref('')
const kind = ref('report')
const sending = ref(false)
const refusal = ref('')
const sent = ref('')
const historyEl = ref(null)
const composerEl = ref(null)

const threads = computed(() => {
  const byKey = new Map()
  for (const channel of board.conversation.channels) {
    byKey.set(`ch:${channel.id}`, {
      key: `ch:${channel.id}`,
      group: 'channel',
      label: `#${channel.id}`,
      gated: Boolean(channel.gated),
      note: channel.rule || '',
      target: { type: 'channel', id: channel.id },
      msgs: [],
    })
  }
  for (const room of board.conversation.rooms) {
    byKey.set(`room:${room.channel}:${room.id}`, {
      key: `room:${room.channel}:${room.id}`,
      group: 'room',
      label: `#${room.channel} / #${room.room}`,
      note: 'a room inherits the parent channel gate; draft by default, publishing is deliberate',
      target: { type: 'room', id: room.id, channel: room.channel },
      msgs: [],
    })
  }
  for (const row of board.conversationRows) {
    const key = row.shape === 'channel'
      ? `ch:${row.channel}`
      : row.shape === 'room'
        ? `room:${row.channel}:${row.room}`
        : `dm:${row.scope}`
    let thread = byKey.get(key)
    if (!thread) {
      thread = row.shape === 'channel'
        ? {
            key, group: 'channel', label: `#${row.channel}`, gated: row.gated,
            note: row.rule, target: { type: 'channel', id: row.channel }, msgs: [],
          }
        : row.shape === 'room'
          ? {
              key, group: 'room', label: `#${row.channel} / #${row.room}`,
              note: row.rule, target: { type: 'room', id: row.room, channel: row.channel }, msgs: [],
            }
          : {
              key, group: 'direct', label: row.scope,
              note: row.rule,
              target: { type: 'direct', peer: row.scope.split(' ⇄ ').find((x) => x !== board.viewer) },
              msgs: [],
            }
      byKey.set(key, thread)
    }
    thread.msgs.push({
      by: row.from,
      to: row.shape === 'channel' ? `#${row.channel}` : row.shape === 'room' ? `#${row.room}` : row.to,
      ts: row.ts,
      body: row.body,
      subject: row.subject,
      id: row.msg_id,
      chips: row.shape === 'channel'
        ? [row.kind && `kind ${row.kind}`, row.responds_to && `responds-to ${row.responds_to}`].filter(Boolean)
        : row.shape === 'room'
          ? (row.mentions || []).map((mention) => `@${mention}`)
          : [row.state, row.ack_required && 'receipt demanded', `${row.bytes} bytes`].filter(Boolean),
    })
  }
  const groupOrder = { channel: 0, room: 1, direct: 2 }
  return [...byKey.values()].sort((a, b) =>
    groupOrder[a.group] - groupOrder[b.group] || (a.label < b.label ? -1 : 1))
})
const groups = computed(() => {
  const g = {}
  for (const t of threads.value) (g[t.group] ||= []).push(t)
  return g
})
// Open on the conversation that moved last, not on whatever happens to be first.
// The leader reads this page to answer the agent that just reported, and a pane
// that opens on a channel whose last message was hours ago makes finding that
// agent a manual job every single time.
const mostRecent = computed(() => {
  const withTs = threads.value.map((t) => ({ t, ts: t.msgs.at(-1)?.ts || '' }))
  withTs.sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0))
  return withTs[0]?.t
})
const current = computed(() => threads.value.find((t) => t.key === picked.value) || mostRecent.value)
watch(current, (t) => { if (t && !picked.value) picked.value = t.key })
const messages = computed(() => {
  const msgs = current.value?.msgs || []
  if (!q.value) return msgs
  const needle = q.value.toLowerCase()
  return msgs.filter((m) => `${m.by} ${m.to} ${m.subject || ''} ${m.body}`.toLowerCase().includes(needle))
})
const dayOf = (ts) => (ts || '').slice(0, 10)
const stamp = (ts) => (ts || '').replace('T', ' ').slice(0, 19)
const preview = (t) => {
  const last = t.msgs[t.msgs.length - 1]
  return (last?.body || '').replace(/[#*`>|\n]+/g, ' ').trim().slice(0, 72) || '(nothing yet)'
}
const body = (text) => md.render(text)

async function openThread(key) {
  picked.value = key
  await nextTick()
  if (historyEl.value) historyEl.value.scrollTop = 0
}
async function jumpToEnd() {
  await nextTick()
  if (historyEl.value) {
    historyEl.value.scrollTo({ top: historyEl.value.scrollHeight, behavior: 'smooth' })
  }
}
function quote(m) {
  drafting.value = `> ${(m.body || '').split('\n').slice(0, 3).join('\n> ')}\n\n`
  composerEl.value?.focus?.()
}

/**
 * The one write path from the browser: it does not write anything itself, it runs
 * `bin/aim` and returns whatever that said. So a write from here lands in the
 * ledger, refuses when the tool refuses, and prints the refusal verbatim.
 */
async function send() {
  if (!drafting.value.trim() || !current.value) return
  sending.value = true
  refusal.value = ''
  sent.value = ''
  const t = current.value.target
  const argv = t.type === 'direct'
    ? ['push', '--to', t.peer, '--subject', `reply from ${board.writer}`, '--body', drafting.value,
       '--via', 'aim dashboard', '--require-ack']
    : ['say', '--channel', t.id, '--kind', kind.value, '--body', drafting.value]
  const res = await api.command(argv)
  sending.value = false
  if (res.rc === 0) {
    sent.value = (res.stdout || '').trim() || 'recorded'
    drafting.value = ''
    await board.load()
    jumpToEnd()
  } else {
    refusal.value = (res.stderr || res.stdout || '').trim() || `exit ${res.rc}`
  }
}
async function copy(text) {
  await navigator.clipboard?.writeText(text)
  ElMessage({ message: 'copied', type: 'success', duration: 1200 })
}
</script>

<template>
  <div class="aim-chat">
    <aside class="aim-chat-side">
      <el-card shadow="never" body-style="padding:8px">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px">
            <span>{{ threads.length }} thread(s)</span>
            <span style="flex:1" />
            <el-tooltip content="re-read the record"><el-button size="small" text @click="board.load()">
              <el-icon><Refresh /></el-icon></el-button></el-tooltip>
          </div>
        </template>
        <div class="aim-thread-list">
          <template v-for="(list, group) in groups" :key="group">
            <div class="aim-dim" style="font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;margin:8px 4px 4px">{{ group }}</div>
            <div v-for="t in list" :key="t.key" class="aim-thread" :class="{ on: t.key === current?.key }"
                 @click="openThread(t.key)">
              <div style="display:flex;align-items:center;gap:6px">
                <span style="font-size:12.5px">{{ t.label }}</span>
                <el-icon v-if="t.gated" style="font-size:11px" title="sealed to you"><Lock /></el-icon>
                <span style="flex:1" />
                <span class="aim-dim" style="font-size:10.5px">{{ (t.msgs.at(-1)?.ts || '').slice(5, 16).replace('T', ' ') }}</span>
              </div>
              <div class="aim-dim" style="font-size:11px;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ preview(t) }}
              </div>
            </div>
          </template>
          <el-empty v-if="!threads.length" description="nothing has been said on the record yet" :image-size="60" />
        </div>
      </el-card>
    </aside>

    <section class="aim-reader">
      <div class="aim-reader-head">
          <strong style="font-size:13.5px">{{ current?.label }}</strong>
          <el-tag v-if="current?.gated" size="small" type="warning" effect="plain">sealed to you</el-tag>
          <span class="aim-dim" style="font-size:11.5px">{{ current?.note }}</span>
          <span style="flex:1" />
          <el-input v-model="q" size="small" placeholder="search in this thread" style="width:180px" clearable />
          <el-button size="small" text @click="jumpToEnd"><el-icon><Bottom /></el-icon> newest</el-button>
        </div>

      <div ref="historyEl" class="aim-history">
        <template v-for="(m, i) in messages" :key="i">
          <div v-if="i === 0 || dayOf(m.ts) !== dayOf(messages[i - 1].ts)" class="aim-daysep">
            {{ dayOf(m.ts) }}
          </div>
          <article class="aim-msg">
            <header>
              <OwnerAvatar :id="m.by" :size="18" />
              <el-icon v-if="m.to" style="font-size:11px"><Right /></el-icon>
              <span v-if="m.to" class="aim-dim">{{ m.to }}</span>
              <span class="aim-dim" style="font-size:11px">{{ stamp(m.ts) }}</span>
              <el-tag v-for="c in (m.chips || []).filter(Boolean)" :key="c" size="small" effect="plain"
                      :type="MAIL_STATE_TYPE[c] || 'info'">{{ c }}</el-tag>
              <span style="flex:1" />
              <el-button size="small" text @click="quote(m)"><el-icon><ChatLineSquare /></el-icon></el-button>
              <el-button size="small" text @click="copy(m.body)"><el-icon><DocumentCopy /></el-icon></el-button>
            </header>
            <div v-if="m.subject" class="aim-subject">{{ m.subject }}</div>
            <div class="markdown-body aim-body" v-html="body(m.body)" />
          </article>
        </template>
        <el-empty v-if="!messages.length" description="this thread is empty" />
      </div>

      <footer class="aim-composer">
        <el-card v-if="!board.canWrite" shadow="never" style="margin-top:4px">
          <div class="aim-dim" style="font-size:12.5px">
            reading as <b>{{ board.viewer }}</b>. this server was started without
            <code class="aim-mono">--allow-write</code>, so there is nothing here to type into:
            a reply box that cannot send is a control that lies about what it does.
          </div>
        </el-card>
        <el-card v-else shadow="never" style="margin-top:4px">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span>reply as <b>{{ board.writer }}</b> to
                <b>{{ current?.target?.type === 'direct' ? current?.target?.peer : '#' + current?.target?.id }}</b></span>
              <el-select v-if="current?.target?.type !== 'direct'" v-model="kind" size="small" style="width:150px">
                <el-option v-for="k in ['report', 'request', 'proposal', 'evidence', 'synthesis']" :key="k" :value="k" :label="k" />
              </el-select>
              <span style="flex:1" />
              <span class="aim-dim" style="font-size:11px">
                runs <code class="aim-mono">aim {{ current?.target?.type === 'direct' ? 'push' : 'say' }}</code> — the dashboard has no writer of its own
              </span>
            </div>
          </template>
          <el-input ref="composerEl" v-model="drafting" type="textarea" :rows="4" resize="vertical"
                    placeholder="markdown is fine. what you send is recorded in the log, hashed, and wakes the peer on their next turn." />
          <div style="display:flex;align-items:center;gap:10px;margin-top:10px">
            <el-button type="primary" :loading="sending" @click="send">send</el-button>
            <span class="aim-dim" style="font-size:11.5px">{{ drafting.length }} characters</span>
            <span style="flex:1" />
          </div>
          <el-alert v-if="refusal" type="error" :closable="false" show-icon style="margin-top:10px"
                    title="the tool refused, and the refusal is recorded">
            <pre class="aim-mono" style="white-space:pre-wrap;margin:6px 0 0">{{ refusal }}</pre>
          </el-alert>
          <el-alert v-if="sent" type="success" :closable="false" show-icon style="margin-top:10px" :title="sent" />
        </el-card>
      </footer>
    </section>
  </div>
</template>
