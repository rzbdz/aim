import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { directScope, useBoard } from '../../src/stores/board'

describe('conversationRows', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('flattens the three conversation shapes into one chronological feed', () => {
    const board = useBoard()
    board.doc = {
      conversation: {
        channels: [{
          id: 'dev',
          gated: true,
          rule: 'sealed',
          messages: [{ from: 'alpha', ts: '2026-09-22T03:00:00Z', body: 'channel' }],
        }],
        rooms: [{
          channel: 'dev',
          id: 'review',
          visibility: 'draft',
          messages: [{ from: 'beta', ts: '2026-09-22T01:00:00Z', body: 'room' }],
        }],
        mail: [{ from: 'alpha', to: 'beta', ts: '2026-09-22T02:00:00Z', body: 'direct' }],
      },
    }

    expect(board.conversationRows.map((row) => [row.shape, row.body])).toEqual([
      ['room', 'room'],
      ['direct', 'direct'],
      ['channel', 'channel'],
    ])
    expect(board.conversationRows[2]).toMatchObject({
      scope: 'dev',
      channel: 'dev',
      room: null,
      gated: true,
      rule: 'sealed',
    })
    expect(board.conversationRows[1]).toMatchObject({
      scope: 'alpha ⇄ beta',
      channel: null,
      room: null,
    })
  })

  it('exposes only phase requests that still match the channel phase', () => {
    const board = useBoard()
    board.doc = {
      channels: [{ id: 'dev', phase: 'SEALED_DIVERGENT', participants: ['alpha', 'beta'], leader: 'human' }],
      conversation: {
        channels: [{
          id: 'dev',
          phase: 'SEALED_DIVERGENT',
          messages: [
            { from: 'alpha', ts: '2026-09-22T04:00:00Z', kind: 'request',
              subject: 'request: SEALED_DIVERGENT -> COMMIT', phase: 'SEALED_DIVERGENT',
              body: 'both positions are sealed' },
            { from: 'beta', ts: '2026-09-22T05:00:00Z', kind: 'request',
              subject: 'request: COMMIT -> SYNTHESIS', phase: 'COMMIT', body: 'stale request' },
          ],
        }],
        rooms: [],
        mail: [],
      },
    }

    expect(board.phaseRequests).toHaveLength(1)
    expect(board.phaseRequests[0]).toMatchObject({
      channel: 'dev',
      fromPhase: 'SEALED_DIVERGENT',
      targetPhase: 'COMMIT',
      currentPhase: 'SEALED_DIVERGENT',
      participants: ['alpha', 'beta'],
    })
  })
})

describe('directScope', () => {
  it('names a pair once, whichever way the message travelled', () => {
    expect(directScope('codex', 'human')).toBe(directScope('human', 'codex'))
    expect(directScope('claude-session1', 'codex')).toBe('claude-session1 ⇄ codex')
    expect(directScope('codex', 'claude-session1')).toBe('claude-session1 ⇄ codex')
  })

  it('keeps two different pairs apart', () => {
    expect(directScope('codex', 'human')).not.toBe(directScope('codex', 'claude-session1'))
  })

  it('folds a two-way exchange into one conversation', () => {
    const board = useBoard()
    board.doc = {
      conversation: {
        channels: [],
        rooms: [],
        mail: [
          { from: 'human', to: 'codex', ts: '2026-09-22T01:00:00Z', body: 'out' },
          { from: 'codex', to: 'human', ts: '2026-09-22T02:00:00Z', body: 'back' },
        ],
      },
    }

    expect(board.conversationRows.map((row) => row.scope)).toEqual([
      'codex ⇄ human',
      'codex ⇄ human',
    ])
  })
})
