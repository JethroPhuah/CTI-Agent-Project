"use client";

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { sendFeedback } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function FeedbackButtons({ runId }: { runId: string }) {
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [busy, setBusy] = useState(false);

  async function rate(v: 1 | -1) {
    if (busy || rating === v) return;
    setBusy(true);
    try {
      await sendFeedback(runId, v);
      setRating(v);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2 mt-3 text-muted">
      <span className="text-xs">Was this useful?</span>
      <button
        onClick={() => rate(1)}
        disabled={busy}
        className={cn(
          "p-1.5 rounded-md transition border border-transparent",
          rating === 1
            ? "bg-good/20 text-good border-good/40"
            : "hover:bg-panel2 hover:text-good"
        )}
        title="Thumbs up"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => rate(-1)}
        disabled={busy}
        className={cn(
          "p-1.5 rounded-md transition border border-transparent",
          rating === -1
            ? "bg-bad/20 text-bad border-bad/40"
            : "hover:bg-panel2 hover:text-bad"
        )}
        title="Thumbs down"
      >
        <ThumbsDown size={14} />
      </button>
      {rating !== null && (
        <span className="text-xs text-muted">Saved — thanks!</span>
      )}
    </div>
  );
}
