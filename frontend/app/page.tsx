"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, ShieldHalf } from "lucide-react";

import ToolSelector from "@/components/ToolSelector";
import ChatInput from "@/components/ChatInput";
import MessageBubble, { ChatMessage } from "@/components/MessageBubble";
import { streamChat } from "@/lib/api";
import { AgentStep } from "@/components/AgentTimeline";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function send() {
    if (busy || !input.trim()) return;

    const query = input.trim();
    setInput("");

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
    };
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      steps: [],
      streaming: true,
    };
    setMessages((m) => [...m, userMsg, assistantMsg]);
    setBusy(true);

    try {
      for await (const ev of streamChat(query, selectedTools)) {
        setMessages((cur) =>
          cur.map((m) => (m.id === assistantId ? mergeEvent(m, ev) : m))
        );
      }
    } catch (e: any) {
      setMessages((cur) =>
        cur.map((m) =>
          m.id === assistantId
            ? { ...m, content: `**Error:** ${e?.message || e}`, streaming: false }
            : m
        )
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 px-5 py-3 border-b border-border bg-panel/60 backdrop-blur">
        <ShieldHalf size={22} className="text-accent" />
        <div>
          <div className="font-semibold text-[15px]">
            CTI Agent <span className="text-muted font-normal">— Multi-Agent Threat Intelligence</span>
          </div>
          <div className="text-[11px] text-muted">
            LangGraph · MCP · ReACT · One-shot · RAG · STIX KG
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-muted">
          <Activity size={14} />
          {busy ? "running…" : "idle"}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Sidebar — tool selector */}
        <aside className="w-[300px] border-r border-border p-4 overflow-y-auto bg-bg/40">
          <h2 className="text-sm font-semibold mb-3 text-[#cfd9ff]">Available tools</h2>
          <p className="text-xs text-muted mb-4">
            Toggle MCP tools that the agents are allowed to use for your next query.
          </p>
          <ToolSelector selected={selectedTools} onChange={setSelectedTools} />
        </aside>

        {/* Main chat */}
        <main className="flex-1 flex flex-col min-w-0">
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-6 flex flex-col gap-5"
          >
            {messages.length === 0 && (
              <div className="m-auto text-center text-muted max-w-xl">
                <ShieldHalf size={32} className="text-accent mx-auto mb-3" />
                <h1 className="text-xl font-semibold text-[#dde6ff] mb-2">
                  Ask the CTI Agent
                </h1>
                <p className="text-sm leading-relaxed">
                  This is a multi-agent system. Your query will pass through an
                  Orchestrator → Retrieval → Writer → Validator pipeline, with
                  each step visible below the response. Try one of the suggested
                  questions to get started.
                </p>
              </div>
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>

          <div className="border-t border-border p-4 bg-bg/40">
            <ChatInput
              value={input}
              onChange={setInput}
              onSubmit={send}
              disabled={busy}
              busy={busy}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Merge an SSE event into the streaming assistant message.
// ---------------------------------------------------------------------
function mergeEvent(m: ChatMessage, ev: any): ChatMessage {
  if (ev.type === "run_started") {
    return { ...m, runId: ev.runId };
  }
  if (ev.type === "agent_step") {
    const steps: AgentStep[] = m.steps ? [...m.steps] : [];
    const existing = steps.findIndex((s) => s.node === ev.node);
    const newStep: AgentStep = { node: ev.node, payload: ev.payload, done: true };
    if (existing >= 0) steps[existing] = newStep;
    else steps.push(newStep);
    return { ...m, steps };
  }
  if (ev.type === "final") {
    return {
      ...m,
      content: ev.answer,
      runId: ev.runId,
      durationMs: ev.durationMs,
      streaming: false,
    };
  }
  if (ev.type === "error") {
    return { ...m, content: `**Error:** ${ev.error}`, streaming: false };
  }
  return m;
}
