import { app, BrowserWindow } from "electron";
import {
  DEFAULT_BACKEND_HOST,
  DEFAULT_BACKEND_PORT,
  createBackendUrl,
  findAvailablePort,
  resolveBackendExecutable,
  startBackend,
  stopBackend,
  waitForBackendHealth,
  type BackendProcess,
} from "./backend.js";

let backendProcess: BackendProcess | null = null;
let mainWindow: BrowserWindow | null = null;

async function createMainWindow(): Promise<void> {
  const host = DEFAULT_BACKEND_HOST;
  const port = await findAvailablePort(host, DEFAULT_BACKEND_PORT);
  const executable =
    process.env.MYNOVEL_BACKEND_EXECUTABLE !== undefined
      ? process.env.MYNOVEL_BACKEND_EXECUTABLE
      : resolveBackendExecutable(process.resourcesPath, process.platform);

  backendProcess = startBackend({ executable, host, port });
  try {
    await waitForBackendHealth(createBackendUrl(host, port, "/health"));
  } catch (error) {
    await createStartupErrorWindow(error);
    return;
  }

  const window = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow = window;
  window.once("ready-to-show", () => {
    mainWindow?.show();
  });
  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });
  await window.loadURL(createBackendUrl(host, port));
}

async function createStartupErrorWindow(error: unknown): Promise<void> {
  stopBackend(backendProcess);
  backendProcess = null;
  const message = error instanceof Error ? error.message : String(error);
  const window = new BrowserWindow({
    width: 760,
    height: 420,
    resizable: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow = window;
  await window.loadURL(
    `data:text/plain;charset=utf-8,${encodeURIComponent(`MyNovel could not start\n\n${message}`)}`,
  );
}

app.whenReady().then(() => {
  void createMainWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend(backendProcess);
  backendProcess = null;
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createMainWindow();
  }
});
