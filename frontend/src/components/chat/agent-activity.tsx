/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronRightIcon } from "lucide-react";
import React from "react";
import { cn } from "@/utils/cn";
import { formatDuration, type TurnTiming } from "./turn-timing";

interface AgentActivityProps {
  running: boolean;
  thinking?: boolean;
  interrupted?: boolean;
  defaultOpen?: boolean;
  timing?: TurnTiming;
  toolCount?: number;
  failedCount?: number;
  steps?: React.ReactNode[];
}

export const AgentActivity: React.FC<AgentActivityProps> = ({
  running,
  thinking = false,
  interrupted = false,
  defaultOpen = false,
  timing,
  toolCount = 0,
  failedCount = 0,
  steps = NO_STEPS,
}) => {
  const [userOpen, setUserOpen] = React.useState<boolean>();
  const open = userOpen ?? (running || defaultOpen);
  const now = useNow(running);
  const hasSteps = steps.length > 0;

  const header = running ? (
    <>
      <output className={SHIMMER_CLASS}>
        {thinking ? "Thinking…" : "Working…"}
      </output>
      {timing && (
        <span className="tabular-nums">
          {formatDuration(now - timing.startedAt)}
        </span>
      )}
    </>
  ) : (
    <>
      <span>{doneLabel({ interrupted, timing, toolCount })}</span>
      {failedCount > 0 && (
        <span className="text-(--red-11)">· {failedCount} failed</span>
      )}
    </>
  );

  return (
    <div className="my-1 w-full">
      {hasSteps ? (
        <button
          type="button"
          onClick={() => setUserOpen(!open)}
          aria-expanded={open}
          className="group/activity -mx-1.5 flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-foreground/6 hover:text-foreground focus-visible:outline-1 focus-visible:outline-(--slate-8)"
        >
          {header}
          <ChevronRightIcon
            aria-hidden={true}
            className={cn(
              "size-3 shrink-0 opacity-60 transition-transform group-hover/activity:opacity-100",
              open && "rotate-90",
            )}
          />
        </button>
      ) : (
        <div className="flex items-center gap-1.5 py-0.5 text-xs text-muted-foreground">
          {header}
        </div>
      )}
      {open && hasSteps && (
        <div className="mt-1 mb-2 ml-1.5 flex flex-col gap-1 border-l border-foreground/15 pl-3">
          {steps}
        </div>
      )}
    </div>
  );
};

const NO_STEPS: React.ReactNode[] = [];

const SHIMMER_CLASS =
  "animate-shimmer bg-[linear-gradient(90deg,var(--muted-foreground)_35%,var(--foreground)_50%,var(--muted-foreground)_65%)] bg-size-[200%_100%] bg-clip-text text-transparent motion-reduce:animate-none";

function doneLabel({
  interrupted,
  timing,
  toolCount,
}: {
  interrupted: boolean;
  timing?: TurnTiming;
  toolCount: number;
}): string {
  const duration =
    timing?.finishedAt == null
      ? undefined
      : formatDuration(timing.finishedAt - timing.startedAt);
  if (interrupted) {
    return duration ? `Stopped after ${duration}` : "Stopped";
  }
  if (toolCount === 0) {
    return duration ? `Thought for ${duration}` : "Thought process";
  }
  if (duration) {
    return `Worked for ${duration}`;
  }
  return `Worked through ${toolCount} ${toolCount === 1 ? "step" : "steps"}`;
}

function useNow(ticking: boolean): number {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!ticking) {
      return;
    }
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [ticking]);
  return now;
}
