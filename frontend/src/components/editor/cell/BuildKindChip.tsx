/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Tiny per-cell chip showing the cell's predicted (or actual) outcome
 * in `marimo build`. Reads {@link buildPreviewAtom} for the live
 * static prediction and {@link buildStateAtom} for ground-truth status
 * after a build has run.
 *
 * The chip stays out of the way: it only renders when there's
 * something interesting to say (i.e. the cell is *not* a setup cell
 * and we have at least a static classification). For non-compilable
 * cells we skip it entirely — the rest of the editor already conveys
 * the same information through normal cell badges.
 */

import { useAtomValue } from "jotai";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { buildPreviewAtom, buildStateAtom } from "@/core/build/atoms";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";

interface Props {
  cellId: CellId;
}

interface ChipConfig {
  label: string;
  tooltip: string;
  variant:
    | "default"
    | "defaultOutline"
    | "outline"
    | "secondary"
    | "success"
    | "destructive";
  className?: string;
}

const FINAL_CONFIG: Record<string, ChipConfig> = {
  compiled: {
    label: "loader",
    tooltip: "Compiles to an artifact loader in the built notebook.",
    variant: "success",
  },
  cached: {
    label: "loader",
    tooltip: "Existing artifact reused from the last build.",
    variant: "success",
  },
  elided: {
    label: "elided",
    tooltip: "Removed from the built notebook (no consumer).",
    variant: "secondary",
  },
  kept: {
    label: "verbatim",
    tooltip: "Runs at notebook-load time (depends on a runtime input).",
    variant: "defaultOutline",
  },
};

export const BuildKindChip: React.FC<Props> = ({ cellId }) => {
  const preview = useAtomValue(buildPreviewAtom).get(cellId);
  const status = useAtomValue(buildStateAtom).cellResults.get(cellId);

  const final = status?.final;
  if (final && FINAL_CONFIG[final]) {
    const cfg = FINAL_CONFIG[final];
    return (
      <Tooltip content={cfg.tooltip} delayDuration={300}>
        <Badge
          variant={cfg.variant}
          className={cn(
            "h-4 px-1.5 text-[10px] font-normal leading-none",
            cfg.className,
          )}
        >
          {cfg.label}
        </Badge>
      </Tooltip>
    );
  }

  if (!preview) {
    return null;
  }
  // Don't double-up with the rest of the editor for setup cells.
  if (preview.confidence === "setup") {
    return null;
  }
  // Cells that depend on a runtime input never compile; the editor
  // already shows that they're "live" cells, so the verbatim chip
  // would just be visual noise.
  if (preview.confidence === "non_compilable") {
    return null;
  }

  // Statically-only preview: we know the cell is compilable, but we
  // can't tell what bucket it'll land in until a build runs. Reuse the
  // loader-success colour at lower opacity so the cell reads as
  // "headed for loader-hood" — same green family as the graph view.
  if (
    preview.confidence === "static" ||
    preview.confidence === "unmaterialized"
  ) {
    return (
      <Tooltip
        content="Compilable. Run a build to see whether it becomes a loader, gets elided, or stays verbatim."
        delayDuration={300}
      >
        <Badge
          variant="success"
          className="h-4 px-1.5 text-[10px] font-normal leading-none opacity-60"
        >
          compilable
        </Badge>
      </Tooltip>
    );
  }

  // We have a live-globals-driven prediction. Reuse the final config
  // but dim the chip so users can tell it's still a guess.
  const kind = preview.predictedKind;
  const finalKey =
    kind === "loader" ? "compiled" : kind === "verbatim" ? "kept" : kind;
  const cfg = finalKey ? FINAL_CONFIG[finalKey] : undefined;
  if (!cfg) {
    return null;
  }
  return chipFor(cfg, true);
};

function chipFor(cfg: ChipConfig, predicted: boolean): React.ReactElement {
  return (
    <Tooltip
      content={
        predicted ? `${cfg.tooltip} (predicted from last run)` : cfg.tooltip
      }
      delayDuration={300}
    >
      <Badge
        variant={cfg.variant}
        className={cn(
          "h-4 px-1.5 text-[10px] font-normal leading-none",
          predicted && "opacity-70",
          cfg.className,
        )}
      >
        {cfg.label}
      </Badge>
    </Tooltip>
  );
}
