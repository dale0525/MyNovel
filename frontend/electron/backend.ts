import { spawn, type ChildProcess, type SpawnOptions } from "node:child_process";
import net from "node:net";
import path from "node:path";

export const DEFAULT_BACKEND_HOST = "127.0.0.1";
export const DEFAULT_BACKEND_PORT = 8765;

export type BackendProcess = Pick<ChildProcess, "kill" | "killed" | "once">;
export type SpawnBackend = (
  executable: string,
  args: string[],
  options: SpawnOptions,
) => BackendProcess;

export function backendExecutableName(platform: NodeJS.Platform = process.platform): string {
  return platform === "win32" ? "MyNovelBackend.exe" : "MyNovelBackend";
}

export function resolveBackendExecutable(
  resourcesPath: string,
  platform: NodeJS.Platform = process.platform,
): string {
  return path.join(resourcesPath, "backend", backendExecutableName(platform));
}

export function createBackendArgs(options: { host: string; port: number }): string[] {
  return ["--host", options.host, "--port", String(options.port), "--strict-port", "--no-open"];
}

export function createBackendUrl(host: string, port: number, pathname = "/"): string {
  return new URL(pathname, `http://${host}:${port}`).toString();
}

export async function findAvailablePort(
  host = DEFAULT_BACKEND_HOST,
  startPort = DEFAULT_BACKEND_PORT,
  attempts = 20,
): Promise<number> {
  for (let offset = 0; offset < attempts; offset += 1) {
    const port = startPort + offset;
    if (await canListen(host, port)) {
      return port;
    }
  }
  throw new Error(`No available port found from ${startPort}.`);
}

export function startBackend(options: {
  executable: string;
  host: string;
  port: number;
  spawnBackend?: SpawnBackend;
}): BackendProcess {
  const spawnBackend = options.spawnBackend !== undefined ? options.spawnBackend : spawn;
  return spawnBackend(options.executable, createBackendArgs(options), {
    stdio: "ignore",
    windowsHide: true,
  });
}

export async function waitForBackendHealth(
  healthUrl: string,
  options: { fetchImpl?: typeof fetch; intervalMs?: number; timeoutMs?: number } = {},
): Promise<void> {
  const fetchImpl = options.fetchImpl !== undefined ? options.fetchImpl : fetch;
  const intervalMs = options.intervalMs !== undefined ? options.intervalMs : 250;
  const timeoutMs = options.timeoutMs !== undefined ? options.timeoutMs : 15_000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() <= deadline) {
    try {
      const response = await fetchImpl(healthUrl);
      if (response.ok) {
        return;
      }
    } catch {
      // Backend is still starting.
    }
    await delay(intervalMs);
  }

  throw new Error(`Backend did not become healthy at ${healthUrl}.`);
}

export function stopBackend(backend: BackendProcess | null): void {
  if (backend && !backend.killed) {
    backend.kill();
  }
}

function canListen(host: string, port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, host);
  });
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
