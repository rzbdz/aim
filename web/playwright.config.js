import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testIgnore: /tests\/unit\//,
  timeout: 30_000,
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8799' },
  webServer: {
    // The canonical port (AGENTS.md: "one port, and it is 8777"). This file used
    // to claim a port of its own so the suite could not silently test a server
    // someone left running -- a real concern, which cost the same day it was
    // written. Two things answer it now, and neither is a second port:
    //
    //  1. `aimboard serve` takes 8777 back from a stale server of its own by
    //     reading /proc, so a leftover process is replaced rather than avoided.
    //  2. `/api/revision` says which fabric revision, which bundle, and whether
    //     the bundle is `stale` against the source. The suite's job is to assert
    //     that (`tests/records.spec.js`), which is a stronger statement than
    //     "we started the process ourselves" -- it is the fact the old comment
    //     was reaching for.
    // A second board on a second port is how a finding gets filed against the
    // wrong build: measured three times on 2026-09-22.
    command: 'python3 -u bin/aimboard.py serve --port 8777 --refresh 20 --allow-write',
    url: 'http://127.0.0.1:8777/',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
  },
})
