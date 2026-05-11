"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, Loader2, User } from "lucide-react";
import AgentTimeline, { AgentStep } from "./AgentTimeline";
import FeedbackButtons from "./FeedbackButtons";
import { cn } from "@/lib/utils";

const NEXT_STAGE: Record<string, string> = {
  orchestrator: "Routing the query and planning tools…",
  retrieval:    "Running the ReACT loop, calling MCP tools…",
  writer:       "Drafting the answer with the chosen template…",
  validator:    "Validating the answer against the evidence…",
};

function statusLine(steps?: AgentStep[]): string {
  if (!steps || steps.length === 0) return "Starting up agents…";
  const last = steps[steps.length - 1].node;
  // Predict the *next* stage so the message changes as soon as a step finishes
  const order = ["orchestrator", "retrieval", "writer", "validator"];
  const i = order.indexOf(last);
  const nextNode = i >= 0 && i + 1 < order.length ? order[i + 1] : last;
  return NEXT_STAGE[nextNode] || "Working…";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: AgentStep[];
  runId?: string;
  durationMs?: number;
  streaming?: boolean;
}

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      className={cn(
        "flex gap-3 max-w-3xl",
        isUser ? "self-end flex-row-reverse" : "self-start"
      )}
    >
      <div
        className={cn(
          "shrink-0 w-9 h-9 rounded-full flex items-center justify-center border",
          isUser
            ? "bg-accent/20 border-accent/40 text-accent"
            : "bg-accent2/20 border-accent2/40 text-accent2"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className={cn("flex-1 min-w-0", isUser && "text-right")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 inline-block text-left max-w-full",
            isUser
              ? "bg-accent/10 border border-accent/30"
              : "bg-panel border border-border"
          )}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : message.streaming && !message.content ? (
            <div className="flex items-center gap-2 text-muted text-sm">
              <Loader2 size={14} className="text-accent2 spin" />
              <span>{statusLine(message.steps)}</span>
            </div>
          ) : (
            <div className="markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || ""}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && message.steps && message.steps.length > 0 && (
          <AgentTimeline steps={message.steps} />
        )}

        {!isUser && message.runId && !message.streaming && message.content && (
          <div className="flex items-center gap-3">
            <FeedbackButtons runId={message.runId} />
            {message.durationMs !== undefined && (
              <span className="text-xs text-muted ml-auto">
                {(message.durationMs / 1000).toFixed(1)}s
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
