/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Build panel — the in-editor UI for `marimo build`.
 *
 * Three regions:
 *
 * 1. **Action row** — the primary Build / Cancel button, plus a "force"
 *    toggle so users can force-rewrite cached artifacts.
 * 2. **Progress** — a determinate progress bar (executed / total) and the
 *    current cell name when one is running, plus the active phase label.
 * 3. **Cell list** — every cell in source order, decorated with its
 *    static badge (live preview), an executing/executed marker, and the
 *    final compiled / cached / elided / kept / setup chip once the build
 *    has run.
 * 4. **Result footer** — once the build is done, the compiled-notebook
 *    path and a link to open it in a new tab.
 */

import { useAtom, useAtomValue } from "jotai";
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  ExternalLinkIcon,
  HammerIcon,
  RefreshCwIcon,
  XCircleIcon,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/icons/spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import {
  type BuildCellStatus,
  type BuildPreviewCell,
  type BuildResultSummary,
  buildPreviewAtom,
  buildStateAtom,
} from "@/core/build/atoms";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { scrollCellIntoView } from "@/core/cells/scrollCellIntoView";
import { KnownQueryParams } from "@/core/constants";
import { useRequestClient } from "@/core/network/requests";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { PanelEmptyState } from "./empty-state";

const BuildPanel: React.FC = () => {
  const { getBuildPreview, runBuild, cancelBuild } = useRequestClient();
  const [build, setBuild] = useAtom(buildStateAtom);
  const [preview, setPreview] = useAtom(buildPreviewAtom);
  const notebook = useAtomValue(notebookAtom);
  const [force, setForce] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const refreshPreview = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await getBuildPreview();
      const map = new Map<CellId, BuildPreviewCell>();
      for (const cell of result.cells ?? []) {
        map.set(cell.cellId as CellId, {
          cellId: cell.cellId as CellId,
          name: cell.name,
          displayName: cell.displayName || cell.name,
          predictedKind: cell.predictedKind ?? null,
          confidence: cell.confidence,
        });
      }
      setPreview(map);
    } catch (err) {
      Logger.warn("build preview failed", err);
    } finally {
      setRefreshing(false);
    }
  }, [getBuildPreview, setPreview]);

  // Pull a preview as soon as the panel mounts, and again whenever the
  // build finishes (so a fresh cell that only just gained predictions
  // gets picked up). Keep this cheap: only one in-flight at a time.
  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const isRunning = build.status === "running";

  const handleBuild = async () => {
    if (isRunning) {
      return;
    }
    try {
      await runBuild({ force, outputDir: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start build";
      toast({
        title: "Build failed to start",
        description: message,
        variant: "danger",
      });
    }
  };

  const handleCancel = async () => {
    if (!build.buildId) {
      return;
    }
    try {
      await cancelBuild({ buildId: build.buildId });
      // Optimistically mark cancelled — the runner will confirm with a
      // ``cancelled`` event shortly.
      setBuild((s) => ({ ...s, status: "cancelled" }));
    } catch (err) {
      Logger.warn("cancel build failed", err);
    }
  };

  const total = build.totalCompilable;
  const executed = build.executedCount;
  const progress = total > 0 ? (executed / total) * 100 : 0;

  // Source order from the notebook so the cell list matches what the
  // user sees in the editor; predictions/results are looked up by id.
  const orderedCells = useMemo(
    () =>
      notebook.cellIds.inOrderIds.map((id) => ({
        id,
        name: notebook.cellData[id]?.name ?? "",
      })),
    [notebook.cellIds, notebook.cellData],
  );

  // Pull the best label we have for each cell: ground truth from the
  // running build, then the static preview, then the function name. The
  // reducer-driven status map already carries a display_name from the
  // backend, which is far more useful than the literal `_` that anonymous
  // cells share in source.
  const labelFor = useCallback(
    (id: CellId, fallback: string): string => {
      const fromStatus = build.cellResults.get(id)?.displayName;
      if (fromStatus) {
        return fromStatus;
      }
      const fromPreview = preview.get(id)?.displayName;
      if (fromPreview) {
        return fromPreview;
      }
      return fallback || "_";
    },
    [build.cellResults, preview],
  );

  if (orderedCells.length === 0) {
    return (
      <PanelEmptyState
        title="Nothing to build"
        description="Add some cells, save the notebook, then come back."
        icon={<HammerIcon />}
      />
    );
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <Button
              size="sm"
              variant="outlineDestructive"
              onClick={handleCancel}
              className="flex-1"
            >
              <XCircleIcon className="w-4 h-4 mr-2" />
              Cancel
            </Button>
          ) : (
            <Button
              size="sm"
              variant="default"
              onClick={handleBuild}
              className="flex-1"
            >
              <HammerIcon className="w-4 h-4 mr-2" />
              Build
            </Button>
          )}
          <Tooltip content="Refresh static prediction">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={refreshPreview}
              disabled={refreshing}
            >
              <RefreshCwIcon
                className={cn("w-4 h-4", refreshing && "animate-[spin_0.8s]")}
              />
            </Button>
          </Tooltip>
        </div>

        <label
          htmlFor="build-force-checkbox"
          className="flex items-center gap-2 text-xs text-muted-foreground"
        >
          <Checkbox
            id="build-force-checkbox"
            checked={force}
            onCheckedChange={(v) => setForce(v === true)}
            disabled={isRunning}
          />
          Force rewrite cached artifacts
        </label>

        {(isRunning || build.status === "success") && (
          <div className="flex flex-col gap-1">
            <Progress
              value={progress}
              indeterminate={isRunning && total === 0}
              aria-label="Build progress"
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {build.activePhase ? (
                  <>Phase: <span className="font-mono">{build.activePhase}</span></>
                ) : build.currentCellName ? (
                  <>Running <span className="font-mono">{build.currentCellName}</span></>
                ) : null}
              </span>
              <span>
                {executed}/{total || "?"} cells
              </span>
            </div>
          </div>
        )}

        {build.status === "error" && build.error && (
          <div className="flex items-start gap-2 rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
            <AlertCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div className="flex flex-col">
              <span className="font-semibold">
                {build.error.cellName
                  ? `Cell ${build.error.cellName} failed`
                  : "Build failed"}
              </span>
              <span className="break-words">{build.error.message}</span>
            </div>
          </div>
        )}

        {build.status === "success" && build.result && (
          <BuildResultFooter result={build.result} />
        )}

        <div className="flex flex-col gap-1 pt-1 border-t">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Cells
          </h3>
          {orderedCells.map(({ id, name }) => (
            <CellRow
              key={id}
              cellId={id}
              name={labelFor(id, name)}
              preview={preview.get(id)}
              status={build.cellResults.get(id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

const BuildResultFooter: React.FC<{
  result: BuildResultSummary | undefined;
}> = ({ result }) => {
  if (!result) {
    return null;
  }
  const handleOpen = () => {
    if (!result.compiledNotebook) {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set(KnownQueryParams.filePath, result.compiledNotebook);
    window.open(url.toString(), "_blank", "noopener");
  };
  return (
    <div className="rounded border bg-card p-2 flex flex-col gap-1.5 text-xs">
      <div className="flex items-center gap-1.5 text-(--grass-9)">
        <CheckCircle2Icon className="w-4 h-4" />
        <span className="font-semibold">Build complete</span>
      </div>
      {result.compiledNotebook && (
        <div className="font-mono text-muted-foreground break-all">
          {result.compiledNotebook}
        </div>
      )}
      <div className="text-muted-foreground">
        {result.artifactsWritten} written · {result.artifactsCached} cached
        {result.artifactsDeleted > 0 ? ` · ${result.artifactsDeleted} gc'd` : ""}
      </div>
      {result.compiledNotebook && (
        <Button
          variant="outline"
          size="xs"
          onClick={handleOpen}
          className="self-start"
        >
          <ExternalLinkIcon className="w-3 h-3 mr-1" />
          Open compiled notebook
        </Button>
      )}
    </div>
  );
};

const CellRow: React.FC<{
  cellId: CellId;
  name: string;
  preview?: BuildPreviewCell;
  status?: BuildCellStatus;
}> = ({ cellId, name, preview, status }) => {
  const handleClick = () => {
    scrollCellIntoView(cellId);
  };
  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-accent text-left text-xs"
    >
      <CellKindBadge preview={preview} status={status} />
      <span className="font-mono truncate flex-1">{name || "_"}</span>
      <CellRunStatus status={status} />
    </button>
  );
};

const CellRunStatus: React.FC<{
  status?: BuildCellStatus;
}> = ({ status }) => {
  if (!status) {
    return null;
  }
  if (status.state === "executing") {
    return <Spinner size="small" className="w-3 h-3" />;
  }
  if (status.state === "executed" && status.elapsedMs !== undefined) {
    return (
      <span className="text-muted-foreground tabular-nums">
        {status.elapsedMs.toFixed(0)}ms
      </span>
    );
  }
  if (status.state === "failed") {
    return <XCircleIcon className="w-3 h-3 text-destructive" />;
  }
  return null;
};

const CellKindBadge: React.FC<{
  preview?: BuildPreviewCell;
  status?: BuildCellStatus;
}> = ({ preview, status }) => {
  // Ground truth from a completed build wins over the predicted preview.
  if (status?.final) {
    const cfg = STATUS_CONFIG[status.final] ?? FALLBACK_BADGE;
    return (
      <Tooltip content={cfg.tooltip} delayDuration={250}>
        <Badge variant={cfg.variant} className="font-normal">
          {cfg.label}
        </Badge>
      </Tooltip>
    );
  }
  if (!preview) {
    return <Badge variant="outline" className="font-normal opacity-40">—</Badge>;
  }
  const cfg = previewBadge(preview);
  return (
    <Tooltip content={cfg.tooltip} delayDuration={250}>
      <Badge variant={cfg.variant} className={cn("font-normal", cfg.className)}>
        {cfg.label}
      </Badge>
    </Tooltip>
  );
};

interface BadgeConfig {
  label: string;
  tooltip: string;
  variant: "default" | "defaultOutline" | "outline" | "secondary" | "success" | "destructive";
  className?: string;
}

const FALLBACK_BADGE: BadgeConfig = {
  label: "—",
  tooltip: "Unknown",
  variant: "outline",
};

const STATUS_CONFIG: Record<string, BadgeConfig> = {
  compiled: {
    label: "loader",
    tooltip: "Replaced with an artifact loader in the compiled notebook.",
    variant: "success",
  },
  cached: {
    label: "loader",
    tooltip: "Existing artifact was reused — nothing to rebuild.",
    variant: "success",
  },
  elided: {
    label: "elided",
    tooltip: "Removed from the compiled notebook (no consumer).",
    variant: "secondary",
  },
  kept: {
    label: "verbatim",
    tooltip: "Runs at notebook-load time (depends on a runtime input).",
    variant: "defaultOutline",
  },
  setup: {
    label: "setup",
    tooltip: "Setup cell — runs first at notebook-load time.",
    variant: "outline",
  },
};

function previewBadge(preview: BuildPreviewCell): BadgeConfig {
  if (preview.confidence === "setup") {
    return STATUS_CONFIG.setup ?? FALLBACK_BADGE;
  }
  if (preview.confidence === "non_compilable") {
    return {
      label: "verbatim",
      tooltip: "Depends on a runtime input (mo.ui / mo.cli_args).",
      variant: "defaultOutline",
      className: "opacity-80",
    };
  }
  const finalKey =
    preview.predictedKind === "loader"
      ? "compiled"
      : preview.predictedKind === "verbatim"
        ? "kept"
        : preview.predictedKind;
  const cfg = finalKey ? STATUS_CONFIG[finalKey] : undefined;
  if (cfg) {
    return { ...cfg, className: "opacity-70" };
  }
  // No predicted kind: best we can say is "compilable". Reuse the
  // loader (green / ``success``) variant so this cell reads as
  // "headed for loader-hood" — the dimmed opacity keeps it visibly
  // separate from a confirmed loader badge.
  return {
    label: "compilable",
    tooltip:
      "Statically compilable. Run a build to see whether it becomes a loader, gets elided, or stays verbatim.",
    variant: "success",
    className: "opacity-60",
  };
}

export default BuildPanel;
