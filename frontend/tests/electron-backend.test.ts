// @vitest-environment node
import path from "node:path";
import net from "node:net";
import { describe, expect, test, vi } from "vitest";
import {
  backendExecutableName,
  createBackendArgs,
  createBackendUrl,
  findAvailablePort,
  resolveBackendExecutable,
  startBackend,
  stopBackend,
  waitForBackendHealth,
  type BackendProcess,
} from "../electron/backend";

describe("Electron backend helpers", () => {
  test("uses platform-specific backend executable names", () => {
    expect(backendExecutableName("win32")).toBe("MyNovelBackend.exe");
    expect(backendExecutableName("darwin")).toBe("MyNovelBackend");
    expect(backendExecutableName("linux")).toBe("MyNovelBackend");
  });

  test("resolves backend executable from Electron resources", () => {
    expect(resolveBackendExecutable("C:\\Program Files\\MyNovel\\resources", "win32")).toBe(
      path.join("C:\\Program Files\\MyNovel\\resources", "backend", "MyNovelBackend.exe"),
    );
  });

  test("creates backend args that prevent browser launch and force the selected port", () => {
    expect(createBackendArgs({ host: "127.0.0.1", port: 8765 })).toEqual([
      "--host",
      "127.0.0.1",
      "--port",
      "8765",
      "--strict-port",
      "--no-open",
    ]);
  });

  test("starts backend with hidden child process options", () => {
    const child = {
      killed: false,
      kill: vi.fn(() => true),
      once: vi.fn(),
    } as unknown as BackendProcess;
    const spawnBackend = vi.fn(() => child);

    const started = startBackend({
      executable: "MyNovelBackend.exe",
      host: "127.0.0.1",
      port: 8765,
      spawnBackend,
    });

    expect(started).toBe(child);
    expect(spawnBackend).toHaveBeenCalledWith(
      "MyNovelBackend.exe",
      ["--host", "127.0.0.1", "--port", "8765", "--strict-port", "--no-open"],
      { stdio: "ignore", windowsHide: true },
    );
  });

  test("waits until backend health endpoint responds ok", async () => {
    let attempts = 0;
    const fetchImpl = vi.fn(async () => {
      attempts += 1;
      return { ok: attempts === 2 };
    });

    await waitForBackendHealth(createBackendUrl("127.0.0.1", 8765, "/health"), {
      fetchImpl,
      intervalMs: 1,
      timeoutMs: 100,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("times out a hanging backend health request", async () => {
    const fetchImpl = vi.fn(() => new Promise<Response>(() => {}));

    await expect(
      waitForBackendHealth(createBackendUrl("127.0.0.1", 8765, "/health"), {
        fetchImpl,
        intervalMs: 1,
        requestTimeoutMs: 5,
        timeoutMs: 20,
      }),
    ).rejects.toThrow("Backend did not become healthy");

    expect(fetchImpl).toHaveBeenCalled();
  }, 500);

  test("finds the next available port when the starting port is occupied", async () => {
    const server = await listenOnAvailablePort("127.0.0.1");

    try {
      const address = server.address();
      if (address === null || typeof address === "string") {
        throw new Error("Expected a TCP server address.");
      }

      await expect(findAvailablePort("127.0.0.1", address.port, 2)).resolves.toBe(
        address.port + 1,
      );
    } finally {
      await closeServer(server);
    }
  });

  test("throws when available port attempts are exhausted", async () => {
    const server = await listenOnAvailablePort("127.0.0.1");

    try {
      const address = server.address();
      if (address === null || typeof address === "string") {
        throw new Error("Expected a TCP server address.");
      }

      await expect(findAvailablePort("127.0.0.1", address.port, 1)).rejects.toThrow(
        `No available port found from ${address.port}.`,
      );
    } finally {
      await closeServer(server);
    }
  });

  test("stops a running backend process", () => {
    const child = {
      killed: false,
      kill: vi.fn(() => true),
      once: vi.fn(),
    } as unknown as BackendProcess;

    stopBackend(child);

    expect(child.kill).toHaveBeenCalledWith();
  });
});

function listenOnAvailablePort(host: string): Promise<net.Server> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, host, () => {
      server.off("error", reject);
      resolve(server);
    });
  });
}

function closeServer(server: net.Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}
