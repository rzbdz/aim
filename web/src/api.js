/**
 * The only module that knows the wire shape.
 *
 * Everything the browser is sent has already been through the gate on the
 * server (`aimboard/gate.py`). This file does not filter, hide or re-check: a
 * client-side gate is a suggestion, and the rule this project keeps re-learning
 * is that a suggestion enforced somewhere else is not enforced at all.
 */

export function createApi({ base = '', getViewer } = {}) {
  const url = (path, params = {}) => {
    const q = new URLSearchParams()
    const viewer = getViewer?.()
    if (viewer) q.set('as', viewer)
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') q.set(k, v)
    }
    const qs = q.toString()
    return `${base}${path}${qs ? `?${qs}` : ''}`
  }

  async function getJson(path, params) {
    const res = await fetch(url(path, params), { cache: 'no-store' })
    if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
    return res.json()
  }

  async function post(path, body) {
    const res = await fetch(url(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const text = await res.text()
    let doc = null
    try {
      doc = JSON.parse(text)
    } catch {
      doc = { ok: false, stderr: text }
    }
    return { status: res.status, ...doc }
  }

  return {
    /** The whole board, folded and gated, in one request. */
    state: () => getJson('/api/state'),
    /** Cheap change check. Answered from file metadata, not by rendering. */
    digest: () => getJson('/api/digest'),
    /** Registered agents, for the "whose view is this" selector. */
    agents: () => getJson('/api/agents'),
    /**
     * Run one `aim` command, as the viewer, through the one implementation of the
     * write discipline. The dashboard is a client of `bin/aim`, never a second
     * writer: this is why a write from here lands in the ledger and produces the
     * same refusal text an agent would get.
     */
    command: (argv) => post('/api/command', { argv, as: getViewer?.() }),
  }
}
