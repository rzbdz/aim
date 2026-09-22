import { describe, expect, it } from 'vitest'
import { messageWaiting, threadWaiting } from '../../src/panes/ChatPane.vue'

/**
 * T-0172: the `needs me` filter must be able to match a channel, and the row it
 * keeps must carry the same state.
 *
 * The pane's two predicates are exported for this file alone, because they are
 * the whole rule and the rule is testable without a browser: before the fix,
 * `threadNeedsMe` returned `false` for every channel unconditionally, so `#hello`
 * -- holding an unanswered phase request -- was filtered out of the one view that
 * would have shown it, and the row marker counted only messages addressed to the
 * viewer, which on a channel is always zero.
 *
 * The fixture mirrors the shape the pane builds: a thread has a `group`, a
 * `target` and `msgs`; a channel message is addressed `to: #<channel>` and so
 * never carries the viewer's name.
 */
const thread = (group, target, msgs) => ({ group, key: group, label: `#${group}`, target, msgs })

describe('threadWaiting: the one rule behind the filter and the row marker', () => {
  it('a channel is waiting when its newest message is not the viewer\'s', () => {
    const msgs = [
      { by: 'codex', to: '#hello', state: '' },
      { by: 'human', to: '#hello', state: '' },
      { by: 'codex', to: '#hello', state: '' },
    ]
    expect(threadWaiting(thread('channel', { type: 'channel', id: 'hello' }, msgs), 'human', [])).toBe(true)
  })

  it('a channel whose newest message is the viewer\'s is not waiting on them', () => {
    const msgs = [
      { by: 'codex', to: '#hello', state: '' },
      { by: 'human', to: '#hello', state: '' },
    ]
    expect(threadWaiting(thread('channel', { type: 'channel', id: 'hello' }, msgs), 'human', [])).toBe(false)
  })

  it('an empty channel is not waiting on anybody', () => {
    expect(threadWaiting(thread('channel', { type: 'channel', id: 'dev' }, []), 'human', [])).toBe(false)
  })

  it('a direct thread is waiting when a message is addressed to the viewer and unanswered', () => {
    const msgs = [{ by: 'codex', to: 'claude-session1', state: 'unread' },
                  { by: 'codex', to: 'human', state: 'unread' }]
    expect(threadWaiting(thread('direct', { type: 'direct', peer: 'codex' }, msgs), 'human', [])).toBe(true)
  })

  it('a demand addressed to another agent is not the viewer\'s', () => {
    const msgs = [{ by: 'codex', to: 'claude-session1', state: 'unread' },
                  { by: 'codex', to: 'claude-session1', state: 'unread' }]
    expect(threadWaiting(thread('direct', { type: 'direct', peer: 'codex' }, msgs), 'human', [])).toBe(false)
  })

  it('an answered message is not waiting, whatever it asked for', () => {
    const msgs = [{ by: 'codex', to: 'human', state: 'acked' }]
    expect(threadWaiting(thread('direct', { type: 'direct', peer: 'codex' }, msgs), 'human', [])).toBe(false)
  })

  it('a room reads the unread count the server computes per agent', () => {
    const room = thread('room', { type: 'room', id: 'review', channel: 'dev' }, [])
    const rooms = [{ channel: 'dev', id: 'review', unread: { human: 2 } }]
    expect(threadWaiting(room, 'human', rooms)).toBe(true)
    expect(threadWaiting(room, 'codex', rooms)).toBe(false)
  })
})

describe('messageWaiting', () => {
  it('is addressed-to-the-viewer and not-yet-answered, and nothing else', () => {
    expect(messageWaiting({ to: 'human', state: 'unread' }, 'human')).toBe(true)
    expect(messageWaiting({ to: 'human', state: 'acked' }, 'human')).toBe(false)
    expect(messageWaiting({ to: 'codex', state: 'unread' }, 'human')).toBe(false)
    expect(messageWaiting({ to: '#hello', state: 'unread' }, 'human')).toBe(false)
  })

  it('does not read a chip, because a chip is a fact about the message', () => {
    expect(messageWaiting({ to: 'human', state: 'acked', chips: ['receipt demanded'] }, 'human')).toBe(false)
  })
})
