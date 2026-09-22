/**
 * T-0177 -- "A channel must say what it is for, and scaffolding must not look
 * like work".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T03:30:37.071Z,
 * actor codex), verbatim:
 *
 *   "The conversation list and the channel header show the channel's topic and
 *    its participants, so a reader can tell a transport test from the project.
 *    The topic is already in the payload at channels[].topic and is dropped by
 *    the conversation view ... Four of the five channels are scaffolding (dev,
 *    hello, s2-scratch, s2-scratch2, barrier-v0) and none of them says so."
 *
 * and the acceptance criteria its `commented` follow-up (2026-09-22T03:32:57.126Z)
 * narrows it to:
 *
 *   "1. Wherever the front-end renders a channel -- picker, list, chat header --
 *    it renders `topic`. 2. A channel with no tasks and no messages is visibly
 *    scaffolding, not a peer of a channel with 71 work items. Pick your own
 *    affordance (a tag, a section, de-emphasis) but the difference must be
 *    visible without clicking. 3. `/chat` states what the channel is for above
 *    the message stream."
 *
 * Revision measured -- `GET http://127.0.0.1:8777/api/revision` on 2026-09-22,
 * before the run below:
 *
 *   fabric d66e004+dirty
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale: true  (the bundle is not built from a clean tree)
 *
 * Everything below is measured on the bundle, by reading the rendered text of
 * `/chat` and of the rows it draws.
 *
 * ---------------------------------------------------------------------------
 * The fixture is built so the two halves of acceptance 2 cannot be satisfied by
 * one weak signal. Three channels, one of each kind the card names:
 *
 *   #hello       71 tasks, 2 messages   the project the card is about
 *   #dev         2 tasks, 0 messages    work, no talk
 *   #s2-scratch2 0 tasks, 0 messages    scaffolding
 *
 * `#dev` is the discriminating one. If the row answers "are there messages", then
 * `#dev` and `#s2-scratch2` read the same, and the surface is answering the wrong
 * question -- the card's question is whether the channel holds *work*. That is
 * asserted directly (`work with no talk is not a probe`), so the test cannot pass
 * on a preview string that happens to say "nothing yet".
 *
 * ---------------------------------------------------------------------------
 * VERDICT: FAIL, all three clauses. Measured on the bundle above, viewer `human`:
 *
 *   1. `/chat` renders no topic anywhere. The sidebar reads
 *      "CHANNEL / #dev / (nothing yet) / #hello / needs me / 09-22 01:05 / b /
 *      #s2-scratch2 / (nothing yet)" and the header reads "#hello / sealed /
 *      newest". The string "Transport test" -- the live `hello` topic -- does not
 *      appear in the rendered text at all. The topic ships in the payload
 *      (`channels[].topic`) and is dropped by the view.
 *   2. The row for `#dev` (2 tasks, 0 messages) and the row for `#s2-scratch2`
 *      (0 tasks, 0 messages) are the same string: the page answers "any
 *      messages?" when the card asks "any work?".
 *   3. `/chat` states nothing about what the channel is for above the stream:
 *      the header carries the id, the gate and the phase note, and no purpose.
 */
import { expect, test } from '@playwright/test'

const TOPIC_HELLO = 'Transport test: can a Claude Code session and a Codex session reach each other'
const TOPIC_DEV = 'aim development: task store, rooms, dashboard'

const note = (from, ts, body) => ({ from, to: 'hello', ts, kind: 'note', body })

const CHANNELS = [
  { id: 'hello', topic: TOPIC_HELLO, phase: 'COMMIT', gated: false, rule: 'sealed to you',
    messages: [note('claude-session1', '2026-09-22T01:00:00.000Z', 'a transport check'),
               note('codex', '2026-09-22T01:05:00.000Z', 'the reply')] },
  // Work and no talk. This is the channel that separates "empty preview" from
  // "holds nothing": it has a task store and no messages.
  { id: 'dev', topic: TOPIC_DEV, phase: 'SEALED_DIVERGENT', gated: false, rule: 'sealed to you', messages: [] },
  // Neither. The scaffolding the card is about.
  { id: 's2-scratch2', topic: '', phase: 'SEALED_DIVERGENT', gated: false, rule: 'sealed to you', messages: [] },
]

const task = (id, channel) => ({
  id, channel, status: 'backlog', provenance: '', owner: 'codex', title: `work ${id}`,
  priority: 'normal', tags: [], blocked_by: [], events: [], comments: [],
})

const TASKS = Object.fromEntries([
  ...Array.from({ length: 71 }, (_, i) => {
    const id = `T-${String(100 + i)}`
    return [id, task(id, 'hello')]
  }),
  ...Array.from({ length: 2 }, (_, i) => {
    const id = `T-0${i}`
    return [id, task(id, 'dev')]
  }),
])

const STATE = {
  digest: 'card-t0177', generated_at: '2026-09-22T03:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'done'], terminal: ['done'], phase: 'RESOLVE', milestones: {},
  agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: TASKS,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer: 'human',
  conversation: { viewer: 'human', is_leader: true, channels: CHANNELS, rooms: [], mail: [], withheld: 0 },
  channels: CHANNELS, unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
}

async function open(page) {
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
  await page.goto('/#/chat')
  await expect(page.locator('.aim-thread-list')).toBeVisible()
}

/** The row of the conversation list for a channel, as the reader sees it. */
// The `.aim-thread` element *is* the aria-labelled control, so the row is selected
// by that attribute rather than by a descendant that does not exist.
const channelRow = (page, id) => page.locator(`.aim-thread[aria-label="Open conversation #${id}"]`)

/**
 * Everything about a row that a reader could use to tell it from its peers.
 *
 * `preview` is the second line on its own, with the channel's own id stripped
 * out: the id is in every row, so comparing whole rows would make any two
 * channels "different" and the assertion would be vacuous.
 */
const rowFacts = (page, id) => channelRow(page, id).evaluate((el) => ({
  label: el.querySelector('span')?.innerText?.trim() || '',
  preview: (el.lastElementChild?.innerText || '').replace(/\s+/g, ' ').trim(),
  tags: [...el.querySelectorAll('.el-tag')].map((t) => t.innerText.trim()),
  classes: [...el.classList].sort(),
  dim: getComputedStyle(el).opacity + '/' + getComputedStyle(el).color,
}))

test.describe('T-0177: a channel says what it is for, and a probe does not look like work', () => {
  test('the conversation list renders each channel topic', async ({ page }) => {
    await open(page)
    const list = await page.locator('.aim-thread-list').innerText()
    expect(list, 'the list carries the topic of the channel that carries the project')
      .toContain(TOPIC_HELLO)
    expect(list, 'and the topic of the channel that carries the development')
      .toContain(TOPIC_DEV)
  })

  test('the chat header states what the channel is for, above the message stream', async ({ page }) => {
    await open(page)
    // Above the stream, not below it: the header is the element that is on screen
    // before the first message is read, which is the whole point of the clause.
    const header = await page.locator('.aim-reader-head').innerText()
    expect(header, 'the header of #hello states its topic').toContain(TOPIC_HELLO)
    // Above the stream, measured as geometry: a topic printed below the last
    // message is not "what this channel is for" to a reader who has just arrived.
    const headBox = await page.locator('.aim-reader-head').boundingBox()
    const streamBox = await page.locator('.aim-history').boundingBox()
    expect(headBox.y, 'the header sits above the message stream').toBeLessThan(streamBox.y)
  })

  test('work with no talk is not a probe: the empty channel is marked as scaffolding', async ({ page }) => {
    // Acceptance 2. `dev` has a task store and no messages; `s2-scratch2` has
    // neither. A surface that draws them the same is answering "are there
    // messages" when the card asks "is there work".
    await open(page)
    const dev = await rowFacts(page, 'dev')
    const scratch = await rowFacts(page, 's2-scratch2')
    const hello = await rowFacts(page, 'hello')

    // The discriminating pair. `dev` holds 2 work items and no messages;
    // `s2-scratch2` holds neither. A row that answers "are there messages" gives
    // them the same second line, and that is the surface answering the wrong
    // question -- this card's question is whether the channel holds work.
    expect(dev.preview, 'the channel with 2 work items must not read as the empty channel')
      .not.toEqual(scratch.preview)
    expect({ tags: scratch.tags, classes: scratch.classes, dim: scratch.dim },
      'the scaffolding channel must be marked as something the working channels are not')
      .not.toEqual({ tags: hello.tags, classes: hello.classes, dim: hello.dim })
    // And the mark has to say it is not work. "(nothing yet)" is a statement about
    // the message log; the card's clause is about the channel's work.
    const marked = [...scratch.tags, scratch.preview].join(' ').toLowerCase()
    expect(marked, 'the scaffolding channel names itself as scaffolding')
      .toMatch(/scaffold|probe|no work|not work|empty channel/)
  })
})
