import { defineConfig } from "@playwright/test";

const host = "127.0.0.1";
const setupPort = 18765;
const workbenchPort = 18766;

export default defineConfig({
  testDir: "./e2e",
  reporter: "list",
  timeout: 30_000,
  projects: [
    {
      name: "setup-gate",
      testMatch: /setup-gate\.spec\.ts/,
      use: { baseURL: `http://${host}:${setupPort}` },
    },
    {
      name: "workbench",
      testMatch: /workbench\.spec\.ts/,
      use: { baseURL: `http://${host}:${workbenchPort}` },
    },
  ],
  webServer: [
    {
      command:
        "python e2e/prepare-fixture.py --profile unconfigured --db ../.mynovel/e2e-unconfigured.sqlite && cd .. && python -m mynovel.dev_server --host 127.0.0.1 --port 18765 --db .mynovel/e2e-unconfigured.sqlite",
      reuseExistingServer: false,
      timeout: 120_000,
      url: `http://${host}:${setupPort}/health`,
    },
    {
      command:
        "python e2e/prepare-fixture.py --profile configured --db ../.mynovel/e2e-configured.sqlite && cd .. && python -m mynovel.dev_server --host 127.0.0.1 --port 18766 --db .mynovel/e2e-configured.sqlite",
      reuseExistingServer: false,
      timeout: 120_000,
      url: `http://${host}:${workbenchPort}/health`,
    },
  ],
});
