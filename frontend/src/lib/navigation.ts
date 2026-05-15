export const APP_NAVIGATION_EVENT = "mynovel:navigate";

export function navigateTo(path: string): void {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new Event(APP_NAVIGATION_EVENT));
}
