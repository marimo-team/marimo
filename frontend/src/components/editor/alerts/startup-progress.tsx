/* Copyright 2026 Marimo. All rights reserved. */
import { AlertCircleIcon, CheckIcon, CircleIcon } from "lucide-react";
import { Spinner } from "@/components/icons/spinner";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import { cn } from "@/utils/cn";

const STEPS = [
  {
    phase: "preparing-environment",
    titles: {
      complete: "Environment ready",
      failed: "Environment setup failed",
      pending: "Preparing environment",
      waiting: "Prepare environment",
    },
    descriptions: {
      complete: "Python and dependencies are available.",
      failed: "Setup could not finish.",
      pending: "Set up Python and dependencies.",
      waiting: "Set up Python and dependencies.",
    },
  },
  {
    phase: "starting-kernel",
    titles: {
      complete: "Kernel ready",
      failed: "Kernel failed to start",
      pending: "Starting kernel",
      waiting: "Start kernel",
    },
    descriptions: {
      complete: "The notebook is ready to run.",
      failed: "The kernel could not connect.",
      pending: "Connecting to this notebook.",
      waiting: "After the environment is ready.",
    },
  },
] as const;

interface StartupProgressProps {
  notice: DisplayConnectionNotice;
  surface: "notebook" | "sidebar";
}

function StartupSummary({ notice, surface }: StartupProgressProps) {
  return (
    <header>
      <output className="sr-only">{notice.title}</output>
      <h2
        className={cn(
          "text-foreground",
          surface === "notebook"
            ? "font-heading text-2xl leading-8 tracking-tight font-normal"
            : "font-prose text-base leading-6 font-bold",
        )}
      >
        {notice.ready
          ? "Your notebook is ready"
          : "Getting your notebook ready"}
      </h2>
      <p
        className={cn(
          "text-muted-foreground",
          surface === "notebook"
            ? "mt-3 text-sm leading-6"
            : "mt-2 text-xs leading-5",
        )}
      >
        {notice.ready
          ? "Your environment and kernel are ready."
          : notice.pending
            ? "Preparing Python and dependencies for this notebook."
            : "Review the setup details below to continue."}
      </p>
    </header>
  );
}

export function ConnectionStatusIcon({
  notice,
}: {
  notice: DisplayConnectionNotice;
}) {
  if (notice.ready) {
    return (
      <CheckIcon
        className="size-4 shrink-0 text-(--grass-11)"
        aria-hidden={true}
      />
    );
  }
  if (notice.pending) {
    return (
      <Spinner
        className="size-4 shrink-0 motion-reduce:animate-none"
        aria-hidden={true}
      />
    );
  }
  return (
    <AlertCircleIcon
      className="size-4 shrink-0 text-(--red-11)"
      aria-hidden={true}
    />
  );
}

export function StartupProgress({ notice, surface }: StartupProgressProps) {
  return (
    <>
      <StartupSummary notice={notice} surface={surface} />
      <ol
        className={cn("space-y-6", surface === "notebook" ? "mt-8" : "mt-6")}
        aria-label="Notebook startup stages"
      >
        {STEPS.map(({ phase, titles, descriptions }, index) => {
          const complete =
            notice.ready || (index === 0 && notice.phase === "starting-kernel");
          const active = !notice.ready && notice.phase === phase;
          const failed = active && !notice.pending;
          const state = complete
            ? "complete"
            : failed
              ? "failed"
              : active
                ? "pending"
                : "waiting";
          return (
            <li
              key={phase}
              aria-current={active ? "step" : undefined}
              className="relative flex items-start gap-3"
            >
              {index === 0 && (
                <span
                  aria-hidden={true}
                  className="absolute left-2 top-6 -bottom-4 border-l border-border"
                />
              )}
              <span
                className={cn(
                  "mt-0.5",
                  complete ? "text-(--grass-11)" : "text-muted-foreground",
                )}
              >
                {complete ? (
                  <CheckIcon className="size-4" aria-hidden={true} />
                ) : active ? (
                  <ConnectionStatusIcon notice={notice} />
                ) : (
                  <CircleIcon
                    className="size-4 text-muted-foreground/50"
                    aria-hidden={true}
                  />
                )}
              </span>
              <div className="min-w-0">
                <div
                  className={cn(
                    "text-sm",
                    failed
                      ? "text-(--red-11)"
                      : complete || active
                        ? "text-foreground"
                        : "text-muted-foreground",
                  )}
                >
                  {titles[state]}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {descriptions[state]}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}
