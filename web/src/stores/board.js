/**
 * The one store. It holds what the server sent, and derives everything else.
 *
 * Derivation lives here rather than in panes for the same reason the gate lives
 * in one place on the server: two panes computing "which tasks are overdue"
 * independently is two answers to one question, and the second one is the one
 * that will be wrong.
 */
import { defineStore } from 'pinia'
import { days, isOverdue, today } from '../theme'

export const useBoard = defineStore('board', {
  state: () => ({
    doc: null,
    viewer: 'human',
    loading: false,
    error: '',
    stale: false,
    fetchedAt: '',
    lastDigest: '',
  }),
  getters: {
    statuses: (s) => s.doc?.statuses || [],
    terminal: (s) => s.doc?.terminal || [],
    phase: (s) => s.doc?.phase || '-',
    milestones: (s) => s.doc?.milestones || {},
    register: (s) => s.doc?.register || {},
    agents: (s) => s.doc?.agents || {},
    tasks(s) {
      return Object.values(s.doc?.tasks || {}).sort((a, b) => (a.id < b.id ? -1 : 1))
    },
    byStatus() {
      const out = {}
      for (const st of this.statuses) out[st] = []
      for (const t of this.tasks) (out[t.status || 'backlog'] ||= []).push(t)
      for (const st of Object.keys(out)) {
        out[st].sort((a, b) => (a.due || '9999') < (b.due || '9999') ? -1 : 1)
      }
      return out
    },
    owners() {
      return [...new Set(this.tasks.map((t) => t.owner).filter(Boolean))].sort()
    },
    tags() {
      return [...new Set(this.tasks.flatMap((t) => t.tags || []))].sort()
    },
    overdue() {
      return this.tasks.filter((t) => isOverdue(t.due, t.status, this.terminal))
    },
    dated() {
      return this.tasks.filter((t) => t.start || t.due)
    },
    /** Tasks a person has actually recorded, as opposed to a plan seed. */
    seedOnly() {
      return this.tasks.filter((t) => (t.provenance || '').includes('seed'))
    },
    recorded() {
      return this.tasks.filter((t) => !(t.provenance || '').includes('seed'))
    },
    horizon() {
      const dates = this.dated.flatMap((t) => [t.start, t.due].filter(Boolean))
      for (const m of Object.values(this.milestones)) if (m.due) dates.push(m.due)
      return dates.sort().length ? [dates.sort()[0], dates.sort().at(-1)] : [today(), today()]
    },
    report: (s) => s.doc?.reports || { series: [], throughput: [], blocked: [], median_cycle: null },
    conversation: (s) => s.doc?.conversation || { channels: [], rooms: [], mail: [], withheld: 0 },
    unacked: (s) => s.doc?.unacked || [],
    drift: (s) => s.doc?.drift || [],
    withheld: (s) => s.doc?.withheld_tasks || 0,
    /** Open blockers, as edges rather than as flags. */
    blockerEdges() {
      const by = Object.fromEntries(this.tasks.map((t) => [t.id, t]))
      const edges = []
      for (const t of this.tasks) {
        for (const b of t.blocked_by || []) {
          const other = by[b] || { id: b, title: '(not in this view)', status: '?' }
          edges.push({ id: t.id, title: t.title, blockedBy: other.id, since: other.title,
                       done: this.terminal.includes(other.status) || other.status === '?' })
        }
      }
      return edges
    },
  },
  actions: {
    async init(api) {
      this.api = api
      const fromUrl = new URLSearchParams(location.search).get('as')
      this.viewer = fromUrl || localStorage.getItem('aim.viewer') || 'human'
      if (fromUrl) localStorage.setItem('aim.viewer', fromUrl)
      await this.load()
    },
    async load() {
      this.loading = true
      try {
        this.doc = await this.api.state()
        this.viewer = this.doc.viewer
        this.lastDigest = this.doc.digest
        this.fetchedAt = new Date().toLocaleTimeString()
        this.stale = false
        this.error = ''
      } catch (err) {
        this.error = String(err.message || err)
      } finally {
        this.loading = false
      }
    },
    async setViewer(who) {
      this.viewer = who
      localStorage.setItem('aim.viewer', who)
      const url = new URL(location.href)
      url.searchParams.set('as', who)
      history.replaceState(null, '', url)
      await this.load()
    },
    /** Cheap: the server answers this from file metadata, not by rendering. */
    async checkDigest() {
      if (document.hidden || !this.api) return
      try {
        const { digest } = await this.api.digest()
        if (digest && digest !== this.lastDigest) this.stale = true
      } catch { /* a dashboard that cannot reach its server should say so on load, not shout here */ }
    },
  },
})

export { days, isOverdue }
