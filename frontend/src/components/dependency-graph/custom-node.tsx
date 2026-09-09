/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React, { memo, use } from "react";
import { Handle, Position } from "reactflow";
import { TinyCode } from "@/components/editor/cell/TinyCode";
import { useCellIds } from "@/core/cells/cells";
import { displayCellName, isInternalCellName } from "@/core/cells/names";
import { cn } from "@/utils/cn";
import {
  type CustomNodeProps,
  INPUTS_HANDLE_ID,
  nodeBodyLines,
  nodeDimensions,
  OUTPUTS_HANDLE_ID,
} from "./elements";
import type { LayoutDirection } from "./types";
import { extractCellPreview } from "./utils/cell-preview";

export const EdgeMarkerContext = React.createContext<LayoutDirection>("LR");

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
  const handleColor = selected ? "var(--gray-9)" : "var(--gray-3)";
  const edgeMarkers = use(EdgeMarkerContext);

  const { width, height } = nodeDimensions(data);
  const isNamed = !isInternalCellName(cell.name);
  const name = displayCellName(cell.name, cellIndex);
  // Only collapsed nodes without defs render the preview; skip the parse
  // otherwise, since it scales with notebook size.
  const preview =
    !data.expanded && data.defs.length === 0
      ? extractCellPreview(cell.code).text
      : undefined;

  return (
    <div>
      <Handle
        type="target"
        id={INPUTS_HANDLE_ID}
        data-testid="input-one"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: handleColor }}
      />
      <Handle
        type="source"
        id={INPUTS_HANDLE_ID}
        data-testid="input-two"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: handleColor }}
      />
      <div
        className={cn(
          "flex flex-col bg-card border border-input/50 rounded-md mx-[2px] overflow-hidden",
          selected && "border-primary",
        )}
        style={{ height, width }}
      >
        <div className="text-xs py-0.5 px-2 bg-muted border-b flex items-center justify-between gap-2 shrink-0">
          <span
            className={cn(
              "truncate",
              isNamed
                ? "font-semibold text-foreground"
                : "text-muted-foreground/70",
            )}
          >
            {name}
          </span>
        </div>
        {data.expanded ? (
          <TinyCode code={cell.code} />
        ) : (
          <div className="flex-1 min-h-0 flex flex-col justify-center px-2 py-1 font-mono text-xs leading-4">
            {data.defs.length > 0 ? (
              // Defs wrapped into comma-separated lines — taller, not wider.
              nodeBodyLines(data).map((line) => (
                <span
                  key={line}
                  className="text-foreground truncate"
                  title={line}
                >
                  {line}
                </span>
              ))
            ) : (
              <span className="truncate italic text-muted-foreground/60">
                {preview ?? "empty"}
              </span>
            )}
          </div>
        )}
      </div>
      <Handle
        type="source"
        id={OUTPUTS_HANDLE_ID}
        data-testid="output-one"
        position={edgeMarkers === "LR" ? Position.Right : Position.Bottom}
        style={{ background: handleColor }}
      />
      <Handle
        type="target"
        id={OUTPUTS_HANDLE_ID}
        data-testid="output-two"
        position={edgeMarkers === "LR" ? Position.Right : Position.Bottom}
        style={{ background: handleColor }}
      />
    </div>
  );
}, EQUALITY_CHECK);
CustomNode.displayName = "CustomNode";

export const nodeTypes = {
  custom: CustomNode,
};
