import { defineConfig } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// Every run gets a fresh demo database; real data in ../data is never touched.
const database = join(mkdtempSync(join(tmpdir(), 'studymate-e2e-')), 'e2e-demo.sqlite3');
const port = 8020;

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  retries: 0,
  // One shared demo database: scenarios run one after another.
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    // Uses the installed Google Chrome; set PW_CHANNEL=chromium in CI.
    channel: process.env.PW_CHANNEL ?? 'chrome',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `cd .. && APP_MODE=demo WORKER_ENABLED=1 DATABASE_PATH=${database} PYTHONPATH=backend .venv/bin/python -m studymate serve --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
