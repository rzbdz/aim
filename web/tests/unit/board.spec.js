import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useBoard } from '../../src/stores/board'

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
})
