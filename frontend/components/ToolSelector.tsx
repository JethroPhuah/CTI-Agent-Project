"use client";

import { useEffect, useState } from "react";
import { fetchTools, type ToolCatalog } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Database, Globe, Search, ShieldCheck } from "lucide-react";

const CATEGORY_META: Record<
  string,
  { label: string; icon: any; color: string }
> = {
  retrieval: { label: "Internal Retrieval", icon: Database, color: "text-accent" },
  search:    { label: "Web Search",          icon: Globe,    color: "text-warn" },
  enrichment:{ label: "IOC Enrichment",      icon: ShieldCheck, color: "text-good" },
  other:     { label: "Other",               icon: Search,   color: "text-muted" },
};

interface Props {
  selected: string[];
  onChange: (tools: string[]) => void;
}

export default function ToolSelector({ selected, onChange }: Props) {
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTools()
      .then((c) => {
        setCatalog(c);
        if (selected.length === 0) onChange(c.tools);
      })
      .catch((e) => setError(String(e.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggle(name: string) {
    if (selected.includes(name)) {
      onChange(selected.filter((t) => t !== name));
    } else {
      onChange([...selected, name]);
    }
  }

  function toggleAll(category: string, names: string[]) {
    const allOn = names.every((n) => selected.includes(n));
    if (allOn) onChange(selected.filter((n) => !names.includes(n)));
    else onChange(Array.from(new Set([...selected, ...names])));
  }

  if (error) {
    return (
      <div className="text-bad text-sm p-3 rounded-lg bg-panel border border-border">
        Failed to load tools: {error}
      </div>
    );
  }

  if (!catalog) {
    return (
      <div className="text-muted text-sm p-3">Discovering MCP tools…</div>
    );
  }

  return (
    <div className="space-y-4">
      {Object.entries(catalog.categorised).map(([cat, names]) => {
        if (!names.length) return null;
        const meta = CATEGORY_META[cat] || CATEGORY_META.other;
        const Icon = meta.icon;
        const allOn = names.every((n) => selected.includes(n));
        return (
          <div key={cat} className="rounded-xl bg-panel border border-border p-3">
            <div className="flex items-center justify-between mb-2">
              <div className={cn("flex items-center gap-2 font-medium", meta.color)}>
                <Icon size={16} />
                {meta.label}
              </div>
              <button
                onClick={() => toggleAll(cat, names)}
                className="text-xs text-muted hover:text-accent transition"
              >
                {allOn ? "Disable all" : "Enable all"}
              </button>
            </div>
            <div className="space-y-1.5">
              {names.map((n) => {
                const on = selected.includes(n);
                return (
                  <label
                    key={n}
                    className={cn(
                      "flex items-center gap-2 text-sm cursor-pointer rounded-md px-2 py-1.5 transition",
                      on ? "bg-panel2 text-white" : "text-muted hover:bg-panel2/60"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(n)}
                      className="accent-accent"
                    />
                    <span className="font-mono text-xs">{n}</span>
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}

      <div className="text-xs text-muted px-1">
        {selected.length} of {catalog.tools.length} tools enabled
      </div>
    </div>
  );
}
