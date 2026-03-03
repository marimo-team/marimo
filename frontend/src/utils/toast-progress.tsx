/* Copyright 2026 Marimo. All rights reserved. */

import { useSyncExternalStore } from "react";
import { Progress } from "@/components/ui/progress";
import type { ProgressState } from "./progress";

interface ToastProgressProps {
  progress: ProgressState;
  showPercentage?: boolean;
}

/**
 * A progress bar component that subscribes to a ProgressState and updates reactively.
 * Designed to be used inside toasts.
 */
export const ToastProgress = ({
  progress,
  showPercentage = false,
}: ToastProgressProps) => {
  const value = useSyncExternalStore(
    (callback) => progress.subscribe(callback),
    () => progress.getProgress(),
  );

  // if we are at 100%, we want to show the indeterminate progress bar
  const isIndeterminate = value === "indeterminate" || value === 100;

  return (
    <div className="mt-2 w-full min-w-[200px]">
      <Progress
        value={isIndeterminate ? undefined : value}
        indeterminate={isIndeterminate}
      />
      {!isIndeterminate && showPercentage && (
        <div className="mt-1 text-xs text-muted-foreground text-right">
          {Math.round(value)}%
        </div>
      )}
    </div>
  );
};
