"use client";

import { useState } from "react";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  Edit3,
  Loader2,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgentStep {
  node: string;
  payload: any;
  done: boolean;
}

const NODE_META: Record<string, { label: string; icon: any; color: string; desc: string }> = {
  orchestrator: {
    label: "Orchestrator",
    icon: Brain,
    color: "text-accent2",
    desc: "Classifies intent → produces a tool plan",
  },
  retrieval: {
    label: "Retrieval (ReACT)",
    icon: Database,
    color: "text-accent",
    desc: "Loops Thought→Action→Observation across MCP tools",
  },
  writer: {
    label: "Writer",
    icon: Edit3,
    color: "text-warn",
    desc: "Selects a one-shot template & drafts the answer",
  },
  validator: {
    label: "Validator",
    icon: ShieldAlert,
    color: "text-good",
    desc: "Verifies answer is grounded in evidence",
  },
};

export default function AgentTimeline({ steps }: { steps: AgentStep[] }) {
  if (steps.length === 0) return null;

  return (
    <div className="space-y-2 mt-3">
      {steps.map((s, i) => (
        <StepCard key={i} step={s} />
      ))}
    </div>
  );
}

function StepCard({ step }: { step: AgentStep }) {
  const meta = NODE_META[step.node] || {
    label: step.node,
    icon: Brain,
    color: "text-muted",
    desc: "",
  };
  const Icon = meta.icon;
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-panel/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 flex items-center gap-2 hover:bg-panel2/60 transition"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Icon size={14} className={meta.color} />
        <span className="text-sm font-medium">{meta.label}</span>
        <span className="text-xs text-muted ml-1 hidden md:inline">
          {meta.desc}
        </span>
        <div className="ml-auto">
          {step.done ? (
            <CheckCircle2 size={14} className="text-good" />
          ) : (
            <Loader2 size={14} className="text-muted spin" />
          )}
        </div>
      </button>

      {open && (
        <div className="px-4 py-3 border-t border-border text-xs text-[#cfd9ff] bg-[#0e1638]">
          <StepBody node={step.node} payload={step.payload} />
        </div>
      )}
    </div>
  );
}

function StepBody({ node, payload }: { node: string; payload: any }) {
  if (node === "orchestrator" && payload.plan) {
    const p = payload.plan;
    return (
      <div className="space-y-2">
        <Field label="Intent" value={p.intent} />
        <Field label="Writer template" value={p.writer_template} />
        <Field
          label="Tools planned"
          value={(p.tools_to_use || []).join(", ") || "(none)"}
        />
        <Field label="Rationale" value={p.rationale} />
        {p.entities && (
          <Field
            label="Entities"
            value={Object.entries(p.entities)
              .filter(([_, v]: any) => Array.isArray(v) && v.length)
              .map(([k, v]: any) => `${k}: ${v.join(", ")}`)
              .join(" | ") || "(none)"}
          />
        )}
      </div>
    );
  }

  if (node === "retrieval") {
    return (
      <div className="space-y-2">
        <Field
          label="Evidence collected"
          value={`${payload.evidence_count ?? 0} item(s)`}
        />
        {(payload.evidence_preview || []).map((e: any, i: number) => (
          <div
            key={i}
            className="rounded border border-border p-2 bg-panel/70"
          >
            <div className="text-accent font-mono text-[11px]">{e.source}</div>
            <div className="text-[12px] text-[#dde6ff]">{e.summary}</div>
          </div>
        ))}
      </div>
    );
  }

  if (node === "writer" && payload.answer_preview) {
    return (
      <div>
        <div className="text-muted mb-1">Answer preview:</div>
        <div className="rounded bg-panel/70 p-2 text-[12px]">
          {payload.answer_preview}…
        </div>
      </div>
    );
  }

  if (node === "validator" && payload.validation) {
    const v = payload.validation;
    return (
      <div className="space-y-2">
        <div
          className={cn(
            "flex items-center gap-2 font-medium",
            v.valid ? "text-good" : "text-bad"
          )}
        >
          {v.valid ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {v.valid ? "Validated" : "Failed validation"}
        </div>
        {v.feedback && <Field label="Feedback" value={v.feedback} />}
        {(v.issues || []).length > 0 && (
          <ul className="list-disc pl-5 text-bad">
            {v.issues.map((iss: string, i: number) => (
              <li key={i}>{iss}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <pre className="whitespace-pre-wrap break-words text-[11px]">
      {JSON.stringify(payload, null, 2)}
    </pre>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted min-w-[110px]">{label}:</span>
      <span className="text-[#e6ecff]">{value}</span>
    </div>
  );
}
