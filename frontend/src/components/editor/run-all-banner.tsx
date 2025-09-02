/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import { XIcon, PlayIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { useRunAllCells } from "./cell/useRunCells";
import type { AppConfig } from "@/core/config/config-schema";
import { notebookAtom } from "@/core/cells/cells";

export const bannerDismissedAtom = atom(false);

export const showRunAllBannerAtom = atom((get) => {
  const notebook = get(notebookAtom);
  const runtimeStates = Object.values(notebook.cellRuntime);
  const bannerDismissed = get(bannerDismissedAtom);

  // Check if all the lastRunStartTimestamp are falsey
  const allStale = runtimeStates.every(
    (runtime) => runtime.status === "idle" && !runtime.lastRunStartTimestamp,
  );

  // Show banner if all cells are stale and user hasn't dismissed it
  return allStale && !bannerDismissed;
});

interface RunAllBannerProps {
  autoInstantiate: boolean;
  width: AppConfig["width"];
}

export const RunAllBanner: React.FC<RunAllBannerProps> = ({
  autoInstantiate,
}) => {
  const showBanner = useAtomValue(showRunAllBannerAtom);
  const setBannerDismissed = useSetAtom(bannerDismissedAtom);
  const runAllCells = useRunAllCells();

  // Don't show banner if auto-instantiate is on
  if (autoInstantiate || !showBanner) {
    return null;
  }

  const handleDismiss = () => {
    setBannerDismissed(true);
  };

  const handleRunAll = () => {
    runAllCells();
    setBannerDismissed(true);
  };
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 bg-[var(--blue-3)]",
        "border border-[var(--blue-6)]",
        "px-6 py-2.5 text-sm text-[var(--blue-11)] mb-2",
      )}
    >
      <div className="flex items-center gap-2.5">
        <PlayIcon className="h-4 w-4 text-[var(--blue-9)]" />
        <span className="font-medium">Ready to run your notebook</span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRunAll}
          className="h-7 px-3 text-[var(--blue-11)] hover:bg-[var(--blue-4)] hover:text-[var(--blue-12)]"
          data-testid="run-all-banner-run-all"
        >
          Run all
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={handleDismiss}
          className="h-7 w-7 p-0 text-[var(--blue-9)] hover:bg-[var(--blue-4)] hover:text-[var(--blue-12)]"
        >
          <XIcon className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
};
