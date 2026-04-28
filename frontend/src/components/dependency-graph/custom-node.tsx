/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React, { memo, use } from "react";
import { Handle, Position, useStore } from "reactflow";
import { TinyCode } from "@/components/editor/cell/TinyCode";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { buildPreviewAtom, buildStateAtom } from "@/core/build/atoms";
import { type CellBuildKind, cellBuildKind } from "@/core/build/cell-kind";
import { useCellIds } from "@/core/cells/cells";
import { displayCellName } from "@/core/cells/names";
import { cn } from "@/utils/cn";
import {
  type CustomNodeProps,
  getNodeHeight,
  INPUTS_HANDLE_ID,
  OUTPUTS_HANDLE_ID,
} from "./elements";
import type { LayoutDirection } from "./types";

function getWidth(canvasWidth: number) {
  const minWidth = 100;
  const maxWidth = 400;
  const padding = 50;
  return Math.min(Math.max(canvasWidth - padding * 2, minWidth), maxWidth);
}

export const EdgeMarkerContext = React.createContext<LayoutDirection>("LR");

/**
 * Whether nodes should recolor themselves to reflect their predicted /
 * actual outcome in `marimo build`. Off by default; enabled by the
 * "Show build status" graph-toolbar checkbox.
 */
export const BuildStatusContext = React.createContext<boolean>(false);

/**
 * Per-{@link CellBuildKind} node styling when build-status mode is on.
 * Picks Radix scale 4 backgrounds + scale 9 borders so the node colour
 * pops at the small zoom levels the dependency graph is usually viewed
 * at (Radix scale 1–2 backgrounds are designed for large surfaces and
 * almost vanish on a 200 × 80 px node).
 *
 * - ``loader``/``compilable`` → ``--grass-*`` (Badge ``success``)
 * - ``verbatim``/``non_compilable`` → ``--blue-*`` (Badge ``defaultOutline``)
 * - ``elided`` → ``--gray-*`` (Badge ``secondary``)
 * - ``setup`` → ``--amber-*``
 *
 * ``compilable`` is "predicted loader, no build run yet" — same family
 * as ``loader``, two steps lighter so a real compiled loader still
 * stands out from the prediction.
 */
const BUILD_KIND_NODE_STYLES: Record<CellBuildKind, string> = {
  loader: "border-(--grass-9) bg-(--grass-4)",
  compilable: "border-(--grass-8) bg-(--grass-2)",
  elided: "border-(--gray-7) bg-(--gray-3)/80 opacity-70",
  verbatim: "border-(--blue-9) bg-(--blue-4)",
  non_compilable: "border-(--blue-9) bg-(--blue-4)",
  setup: "border-(--amber-9) bg-(--amber-4)",
};

/**
 * Badge variants for the in-node chip. Mirrors the Build panel's
 * {@link STATUS_CONFIG} so users see the exact same coloured pill in
 * both places.
 */
const BUILD_KIND_BADGE_VARIANT: Record<CellBuildKind, BadgeProps["variant"]> = {
  loader: "success",
  compilable: "success",
  elided: "secondary",
  verbatim: "defaultOutline",
  non_compilable: "defaultOutline",
  setup: "outline",
};

// Both ``verbatim`` and ``non_compilable`` end up as "kept" cells in
// the compiled notebook — the difference (one was predicted by live
// data, the other is structurally non-compilable) is a backend detail
// that's surfaced in the chip's tooltip rather than its label, to
// match the Build panel's convention.
const BUILD_KIND_LABEL: Record<CellBuildKind, string> = {
  loader: "loader",
  elided: "elided",
  verbatim: "verbatim",
  setup: "setup",
  compilable: "compilable",
  non_compilable: "verbatim",
};

const EQUALITY_CHECK = (
  prevProps: CustomNodeProps,
  nextProps: CustomNodeProps,
) => {
  const keys: (keyof CustomNodeProps)[] = ["data", "selected", "id"];
  return keys.every((key) => prevProps[key] === nextProps[key]);
};

export const CustomNode = memo((props: CustomNodeProps) => {
  const { data, selected } = props; // must match the equality check
  const cell = useAtomValue(data.atom);
  const cellIndex = useCellIds().inOrderIds.indexOf(cell.id);
  const showBuildStatus = use(BuildStatusContext);
  const buildState = useAtomValue(buildStateAtom);
  const preview = useAtomValue(buildPreviewAtom);
  const nonSelectedColor = "var(--gray-3)";
  const selectedColor = "var(--gray-9)";
  const color = selected ? selectedColor : nonSelectedColor;
  const reactFlowWidth = useStore(({ width }) => width);
  const edgeMarkers = use(EdgeMarkerContext);

  const buildKind = showBuildStatus
    ? cellBuildKind(cell.id, buildState, preview)
    : undefined;
  const buildNodeClasses = buildKind
    ? BUILD_KIND_NODE_STYLES[buildKind]
    : undefined;
  const buildBadgeVariant = buildKind
    ? BUILD_KIND_BADGE_VARIANT[buildKind]
    : undefined;
  const buildLabel = buildKind ? BUILD_KIND_LABEL[buildKind] : undefined;
  // ``compilable`` is "we *think* this becomes a loader, but no build
  // has run yet" — dim the chip + node so users can tell prediction
  // from ground truth at a glance.
  const isPredictedOnly = buildKind === "compilable";

  const linesOfCode = cell.code.split("\n").length;
  return (
    <div>
      <Handle
        type="target"
        id={INPUTS_HANDLE_ID}
        data-testid="input-one"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: color }}
      />
      <Handle
        type="source"
        id={INPUTS_HANDLE_ID}
        data-testid="input-two"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: color }}
      />
      <div
        className={cn(
          "flex flex-col bg-card border border-input/50 rounded-md mx-[2px] overflow-hidden transition-colors",
          buildNodeClasses,
          selected && "border-primary",
        )}
        style={{
          height: getNodeHeight(linesOfCode),
          width: data.forceWidth || getWidth(reactFlowWidth),
        }}
      >
        <div className="flex items-center gap-2 text-muted-foreground font-semibold text-xs py-1 px-2 bg-muted border-b">
          <span className="truncate flex-1">
            {displayCellName(cell.name, cellIndex)}
          </span>
          {buildLabel && buildBadgeVariant && (
            <Badge
              data-testid="build-kind-chip"
              variant={buildBadgeVariant}
              className={cn(
                "h-4 px-1.5 text-[10px] font-normal leading-none",
                isPredictedOnly && "opacity-70",
              )}
            >
              {buildLabel}
            </Badge>
          )}
        </div>
        <TinyCode code={cell.code} />
      </div>
      <Handle
        type="source"
        id={OUTPUTS_HANDLE_ID}
        data-testid="output-one"
        position={edgeMarkers === "LR" ? Position.Right : Position.Bottom}
        style={{ background: color }}
      />
      <Handle
        type="target"
        id={OUTPUTS_HANDLE_ID}
        data-testid="output-two"
        position={edgeMarkers === "LR" ? Position.Right : Position.Bottom}
        style={{ background: color }}
      />
    </div>
  );
}, EQUALITY_CHECK);
CustomNode.displayName = "CustomNode";

export const nodeTypes = {
  custom: CustomNode,
};
