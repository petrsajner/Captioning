// Browser UI suite: `npm run test:ui`. Uses the system Microsoft Edge, so no browser download is needed.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/ui',
  globalSetup: './tests/ui/global-setup.js',
  // One app instance and one profile: tests run in order and reset the state they need.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  use: {
    channel: 'msedge',
    viewport: { width: 1480, height: 940 },
    screenshot: 'only-on-failure',
  },
});
