export type LlmStreamEvent<TDone extends Record<string, unknown> = Record<string, unknown>> =
  | {
      type: "started" | "stage" | "chunk" | "applying";
      message?: unknown;
      text?: unknown;
      [key: string]: unknown;
    }
  | ({
      type: "done";
      message?: unknown;
      [key: string]: unknown;
    } & TDone)
  | {
      type: "failed";
      message?: unknown;
      [key: string]: unknown;
    };

export function streamPreviewLine(text: string): string {
  const chineseSegments = text.match(/[\u3400-\u9fff][\u3400-\u9fff0-9，。！？、；：：“”‘’（）《》\s-]*/g);
  const source = chineseSegments?.join(" ") ?? text.replace(/[A-Za-z_{}[\]"':,]/g, " ");
  const normalized = source.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  return normalized.length > 56 ? `${normalized.slice(0, 56)}...` : normalized;
}

export function streamEventPreview(event: LlmStreamEvent): string {
  if (!["started", "stage", "chunk", "applying"].includes(event.type)) {
    return "";
  }
  const text = typeof event.text === "string" && event.text.trim()
    ? event.text
    : typeof event.message === "string"
      ? event.message
      : "";
  return streamPreviewLine(text);
}

export function nextStreamSnippets(current: string[], snippet: string, limit = 2): string[] {
  const normalized = snippet.trim();
  if (!normalized) {
    return current;
  }
  return [...current, normalized].slice(-limit);
}

