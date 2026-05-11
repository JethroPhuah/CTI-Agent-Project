// Client for the FastAPI backend.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ToolCatalog {
  tools: string[];
  categorised: Record<string, string[]>;
}

export async function fetchTools(): Promise<ToolCatalog> {
  const res = await fetch(`${API_URL}/tools`, { cache: "no-store" });
  if (!res.ok) throw new Error(`tools fetch failed: ${res.status}`);
  return res.json();
}

export async function sendFeedback(
  runId: string,
  rating: 1 | -1,
  comment = ""
): Promise<void> {
  await fetch(`${API_URL}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, rating, comment }),
  });
}

// ----------------------------------------------------------------------
// Streaming chat (SSE via fetch + ReadableStream).
// We POST the body and parse the SSE stream from the response.
// ----------------------------------------------------------------------

export type StreamEvent =
  | { type: "run_started"; runId: string; availableTools: string[] }
  | { type: "agent_step"; node: string; payload: any }
  | { type: "final"; runId: string; answer: string; durationMs: number; validation?: any }
  | { type: "error"; error: string };

export async function* streamChat(
  query: string,
  selectedTools: string[]
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ query, selected_tools: selectedTools }),
    cache: "no-store",
  });
  if (!res.body) throw new Error("no response body");
  if (!res.ok) throw new Error(`chat returned ${res.status}: ${await res.text()}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalize CRLF to LF so split-on-blank-line works regardless of server
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    // SSE messages are separated by a blank line ("\n\n")
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const trimmed = chunk.trim();
      if (!trimmed) continue;

      let event = "message";
      const dataLines: string[] = [];
      for (const line of trimmed.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
        // Ignore "id:" "retry:" and ":" comment lines
      }
      const data = dataLines.join("\n");
      if (!data) continue;

      let parsed: any;
      try {
        parsed = JSON.parse(data);
      } catch (e) {
        console.warn("[sse] bad JSON, skipping:", data.slice(0, 200), e);
        continue;
      }

      switch (event) {
        case "run_started":
          yield { type: "run_started", runId: parsed.run_id, availableTools: parsed.available_tools || [] };
          break;
        case "agent_step":
          yield { type: "agent_step", node: parsed.node, payload: parsed };
          break;
        case "final":
          yield { type: "final", runId: parsed.run_id, answer: parsed.answer, durationMs: parsed.duration_ms, validation: parsed.validation };
          break;
        case "error":
          yield { type: "error", error: parsed.error };
          break;
        default:
          // Ignore unknown event names instead of silently dropping
          if (process.env.NODE_ENV !== "production") {
            console.debug("[sse] unhandled event", event, parsed);
          }
      }
    }
  }
}
