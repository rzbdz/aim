// Re-export the real store with the extensionless import rewritten for node.
import { readFileSync } from 'node:fs'
const src = readFileSync('/root/tmp/agent-im/web/src/stores/board.js', 'utf8')
const rewritten = src.replace(/from '\.\.\/theme'/, "from './theme.mjs'")
const url = 'data:text/javascript;base64,' + Buffer.from(rewritten).toString('base64')
const mod = await import(url)
export const useBoard = mod.useBoard
export const directScope = mod.directScope
export const isPromise = mod.isPromise
