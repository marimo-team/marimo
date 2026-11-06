/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { stagedAICellsAtom } from "@/core/ai/staged-cells";
import { cn } from "@/utils/cn";

export function PendingAIChangesBadge({ className }: { className?: string }) {
  const count = useAtomValue(stagedAICellsAtom).size;
  if (count === 0) {
    return null;
  }
  return (
    <span
      className={cn(
        "inline-flex h-4 min-w-4 items-center justify-center rounded-full border border-border bg-muted px-1 text-[10px] leading-none tabular-nums text-foreground",
        className,
      )}
    >
      <span aria-hidden={true}>{count}</span>
      <span className="sr-only">
        {count} pending AI {count === 1 ? "change" : "changes"}
      </span>
    </span>
  );
}
