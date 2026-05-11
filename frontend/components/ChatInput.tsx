"use client";

import { Send, StopCircle } from "lucide-react";
import { useEffect, useRef } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  busy?: boolean;
  onStop?: () => void;
}

const SUGGESTIONS = [
  "What tools does APT41 use?",
  "Summarize the latest LockBit campaign",
  "Is 185.12.45.78 malicious?",
  "Are FIN7 and LockBit connected?",
];

export default function ChatInput({
  value, onChange, onSubmit, disabled, busy, onStop,
}: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 180) + "px";
    }
  }, [value]);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSubmit();
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onChange(s)}
            disabled={disabled}
            className="text-xs text-muted hover:text-accent border border-border bg-panel/60 px-3 py-1 rounded-full transition disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
      <div className="flex gap-2 items-end bg-panel rounded-2xl border border-border p-2 focus-within:border-accent transition">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask anything about threat actors, IOCs, recent campaigns…"
          rows={1}
          className="flex-1 bg-transparent outline-none resize-none px-2 py-1.5 text-[15px]"
          disabled={disabled}
        />
        {busy && onStop ? (
          <button
            onClick={onStop}
            className="bg-bad/20 hover:bg-bad/30 text-bad px-3 py-2 rounded-xl flex items-center gap-1.5 transition"
          >
            <StopCircle size={16} /> Stop
          </button>
        ) : (
          <button
            onClick={onSubmit}
            disabled={disabled || !value.trim()}
            className="bg-accent hover:bg-accent/80 disabled:bg-panel2 disabled:text-muted text-white px-4 py-2 rounded-xl flex items-center gap-1.5 transition"
          >
            <Send size={16} /> Send
          </button>
        )}
      </div>
    </div>
  );
}
