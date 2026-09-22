import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testIgnore: /tests\/unit\//,
  timeout: 30_000,
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8799' },
  webServer: {
    // A port of its own, and `reuseExistingServer` only when it is *our* server
    // that is still up. On a shared port the suite silently tested whatever was
    // already listening there: a server started before the last `npm run build`
    // serves the previous bundle, so a failing assertion can be a fact about the
    // front-end or a fact about a process someone left running an hour ago, and
    // the runner cannot tell you which. That ambiguity is what makes a
    // front-end suite stop being evidence.
    command: 'python3 -u bin/aimboard.py serve --port 8799 --refresh 20 --allow-write',
    url: 'http://127.0.0.1:8799/',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
  },
})
