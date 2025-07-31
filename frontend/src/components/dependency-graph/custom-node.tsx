/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React, { memo, use } from "react";
import { Handle, Position, useStore } from "reactflow";
import { TinyCode } from "@/components/editor/cell/TinyCode";
import { useCellIds } from "@/core/cells/cells";
import { displayCellName } from "@/core/cells/names";
import { cn } from "@/utils/cn";
import { type CustomNodeProps, getNodeHeight } from "./elements";
import type { LayoutDirection } from "./types";

function getWidth(canvasWidth: number) {
  const minWidth = 100;
  const maxWidth = 400;
  const padding = 50;
  return Math.min(Math.max(canvasWidth - padding * 2, minWidth), maxWidth);
}

export const EdgeMarkerContext = React.createContext<LayoutDirection>("LR");

const EQUALITY_CHECK = (
  prevProps: CustomNodeProps,
  nextProps: CustomNodeProps,
) => {
  const keys: Array<keyof CustomNodeProps> = ["data", "selected", "id"];
  return keys.every((key) => prevProps[key] === nextProps[key]);
};

export const CustomNode = memo((props: CustomNodeProps) => {
  const { data, selected } = props; // must match the equality check
  const cell = useAtomValue(data.atom);
  const cellIndex = useCellIds().inOrderIds.indexOf(cell.id);
  const nonSelectedColor = "var(--gray-3)";
  const selectedColor = "var(--gray-9)";
  const color = selected ? selectedColor : nonSelectedColor;
  const reactFlowWidth = useStore(({ width }) => width);
  const edgeMarkers = use(EdgeMarkerContext);

  const linesOfCode = cell.code.split("\n").length;
  return (
    <div>
      <Handle
        type="target"
        id="inputs"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: color }}
      />
      <Handle
        type="source"
        id="inputs"
        position={edgeMarkers === "LR" ? Position.Left : Position.Top}
        style={{ background: color }}
      />
      <div
        className={cn(
          "flex flex-col bg-card border border-input/50 rounded-md mx-[2px] overflow-hidden",
          selected && "border-primary",
        )}
        style={{
          height: getNodeHeight(linesOfCode),
          width: data.forceWidth || getWidth(reactFlowWidth),
        }}
      >
        <div className="text-muted-foreground font-semibold text-xs py-1 px-2 bg-muted border-b">
          {displayCellName(cell.name, cellIndex)}
        </div>
        <TinyCode code={cell.code} />
      </div>
      <Handle
        type="source"
        id="outputs"
        position={edgeMarkers === "LR" ? Position.Right : Position.Bottom}
        style={{ background: color }}
      />
      <Handle
        type="target"
        id="outputs"
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
