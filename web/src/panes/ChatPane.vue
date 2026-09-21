<script setup>
import { computed, inject, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useBoard } from '../stores/board'
import OwnerAvatar from '../components/OwnerAvatar.vue'
import { MAIL_STATE_TYPE } from '../theme'

/**
 * Reading the conversation is the point of this pane, so the layout is a
 * *document*, not a widget: the page scrolls, messages flow at a readable measure,
 * and nothing is trapped inside a nested scroll box. The first version put the
 * thread inside `el-scrollbar` with a `max-height`, which is a scroll container
 * whose height resolves to auto - so it clipped the end of every long report and
 * could not be scrolled at all. Reading the record is not a panel; it is the page.
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

const threads = computed(() => {
  const out = []
  for (const ch of board.conversation.channels) {
    out.push({
      key: `ch:${ch.id}`, group: 'channel', label: `#${ch.id}`, gated: ch.gated,
      sub: `${ch.messages.length} message(s) · ${ch.gated ? 'sealed to you' : 'open'}`,
      note: ch.rule, target: { type: 'channel', id: ch.id },
      msgs: ch.messages.map((m) => ({ by: m.from, to: `#${ch.id}`, ts: m.ts, body: m.body,
        chips: [m.kind && `kind ${m.kind}`, m.responds_to && `responds-to ${m.responds_to}`].filter(Boolean) })),
    })
  }
  for (const r of board.conversation.rooms) {
    out.push({
      key: `room:${r.channel}:${r.id}`, group: 'room', label: `#${r.channel} / #${r.id}`,
      sub: `${r.messages.length} message(s) · ${r.visibility}`,
      note: 'a room inherits the parent channel gate; draft by default, publishing is deliberate',
      target: { type: 'room', id: r.id, channel: r.channel },
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
      key: `dm:${key}`, group: 'direct', label: key, sub: `${msgs.length} message(s)`,
      note: 'a direct message is a durable record with a receipt, not a chat window',
      target: { type: 'direct', peer: key.split(' ⇄ ').find((x) => x !== board.viewer) },
      msgs: [...msgs].sort((a, b) => (a.ts < b.ts ? -1 : 1)).map((m) => ({
        by: m.from, to: m.to, ts: m.ts, body: m.body, subject: m.subject, id: m.msg_id,
        chips: [m.state, m.ack_required && 'receipt demanded', `${m.bytes} bytes`].filter(Boolean),
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

const main = () => document.querySelector('.el-main')
async function openThread(key) {
  picked.value = key
  await nextTick()
  main()?.scrollTo({ top: 0 })
}
async function jumpToEnd() {
  await nextTick()
  const el = main()
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}
function quote(m) {
  drafting.value = `> ${(m.body || '').split('\n').slice(0, 3).join('\n> ')}\n\n`
  document.getElementById('aim-composer')?.focus()
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
  <el-row :gutter="16">
    <el-col :span="7">
      <div class="aim-side">
      <el-card shadow="never" body-style="padding:8px">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px">
            <span>{{ threads.length }} thread(s)</span>
            <span style="flex:1" />
            <el-tooltip content="re-read the record"><el-button size="small" text @click="board.load()">
              <el-icon><Refresh /></el-icon></el-button></el-tooltip>
          </div>
        </template>
        <div style="max-height:calc(100vh - 230px);overflow:auto">
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
      </div>
    </el-col>

    <el-col :span="17">
      <div class="aim-reader">
        <div class="aim-reader-head">
          <strong style="font-size:13.5px">{{ current?.label }}</strong>
          <el-tag v-if="current?.gated" size="small" type="warning" effect="plain">sealed to you</el-tag>
          <span class="aim-dim" style="font-size:11.5px">{{ current?.note }}</span>
          <span style="flex:1" />
          <el-input v-model="q" size="small" placeholder="search in this thread" style="width:180px" clearable />
          <el-button size="small" text @click="jumpToEnd"><el-icon><Bottom /></el-icon> newest</el-button>
        </div>

        <template v-for="(m, i) in messages" :key="i">
          <div v-if="i === 0 || dayOf(m.ts) !== dayOf(messages[i - 1].ts)" class="aim-daysep">{{ dayOf(m.ts) }}</div>
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

        <div class="aim-dock">
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
          <el-input id="aim-composer" v-model="drafting" type="textarea" :rows="4" resize="vertical"
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
        </div>
      </div>
    </el-col>
  </el-row>
</template>
