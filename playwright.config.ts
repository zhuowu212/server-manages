import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e', testMatch: '**/*.spec.ts', workers: 1,
  use: { baseURL: 'https://localhost:8443', ignoreHTTPSErrors: true },
});
