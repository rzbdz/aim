import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testIgnore: /tests\/unit\//,
  timeout: 30_000,
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8777' },
  webServer: {
    command: 'python3 -u bin/aimboard.py serve --port 8777 --refresh 20 --allow-write',
    url: 'http://127.0.0.1:8777/',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
  },
})
