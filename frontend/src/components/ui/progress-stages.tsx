/* Copyright 2026 Marimo. All rights reserved. */
import { AlertCircleIcon, CheckIcon, CircleIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Spinner } from "@/components/icons/spinner";
import { cn } from "@/utils/cn";

export type ProgressState = "waiting" | "running" | "succeeded" | "failed";

export interface ProgressStage {
  id: string;
  state: ProgressState;
  title: string;
  description: string;
  details?: ReactNode;
}

export function ProgressStatusIcon({
  state,
  variant = "icon",
}: {
  state: ProgressState;
  variant?: "icon" | "dot";
}) {
  if (variant === "dot") {
    return (
      <span
        aria-hidden={true}
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          {
            waiting: "bg-muted-foreground",
            running: "bg-muted-foreground motion-safe:animate-pulse",
            succeeded: "bg-(--grass-9)",
            failed: "bg-(--red-9)",
          }[state],
        )}
      />
    );
  }
  const Icon = {
    waiting: CircleIcon,
    running: Spinner,
    succeeded: CheckIcon,
    failed: AlertCircleIcon,
  }[state];
  return (
    <Icon
      aria-hidden={true}
      className={cn(
        "size-4 shrink-0",
        {
          waiting: "text-muted-foreground/50",
          running: "motion-reduce:animate-none",
          succeeded: "text-(--grass-11)",
          failed: "text-(--red-11)",
        }[state],
      )}
    />
  );
}

export function ProgressStages({
  stages,
  label,
  className,
}: {
  stages: readonly ProgressStage[];
  label: string;
  className?: string;
}) {
  return (
    <ol aria-label={label} className={cn("space-y-6", className)}>
      {stages.map((stage, index) => (
        <li
          key={stage.id}
          aria-current={
            stage.state === "running" || stage.state === "failed"
              ? "step"
              : undefined
          }
          className="relative flex items-start gap-3"
        >
          {index < stages.length - 1 && (
            <span
              aria-hidden={true}
              className="absolute left-2 top-6 -bottom-4 border-l border-border"
            />
          )}
          <span className="mt-0.5 text-muted-foreground">
            <ProgressStatusIcon state={stage.state} />
          </span>
          <div className="min-w-0 flex-1">
            <div
              className={cn(
                "text-sm",
                stage.state === "failed"
                  ? "text-(--red-11)"
                  : stage.state === "waiting"
                    ? "text-muted-foreground"
                    : "text-foreground",
              )}
            >
              {stage.title}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {stage.description}
            </p>
            {stage.details}
          </div>
        </li>
      ))}
    </ol>
  );
}
