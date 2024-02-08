/* Copyright 2024 Marimo. All rights reserved. */
import { TinyCode } from "@/components/editor/cell/TinyCode";
import { cn } from "@/utils/cn";
import { useAtomValue } from "jotai";
import { memo } from "react";
import { Handle, Position, useStore } from "reactflow";
import { CustomNodeProps, getNodeHeight } from "./elements";
import { displayCellName } from "@/core/cells/names";
import { CellId } from "@/core/cells/ids";
import { useCellIds } from "@/core/cells/cells";

function getWidth(canvasWidth: number) {
  const minWidth = 100;
  const maxWidth = 400;
  const padding = 50;
  return Math.min(Math.max(canvasWidth - padding * 2, minWidth), maxWidth);
}

export const CustomNode = memo((props: CustomNodeProps) => {
  const { data, selected, id } = props;
  const cell = useAtomValue(data.atom);
  const cellIndex = useCellIds().indexOf(id as CellId);
  const nonSelectedColor = "var(--gray-3)";
  const selectedColor = "var(--gray-9)";
  const color = selected ? selectedColor : nonSelectedColor;
  const reactFlowWidth = useStore(({ width }) => width);

  const linesOfCode = cell.code.split("\n").length;
  return (
    <div>
      <Handle
        type="target"
        id="inputs"
        position={Position.Left}
        style={{ background: color }}
      />
      <Handle
        type="source"
        id="inputs"
        position={Position.Left}
        style={{ background: color }}
      />
      <div
        className={cn(
          "flex flex-col bg-card border border-input/50 rounded-md mx-[2px] overflow-hidden",
          selected && "border-primary",
        )}
        style={{
          height: getNodeHeight(linesOfCode),
          width: getWidth(reactFlowWidth),
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
        position={Position.Right}
        style={{ background: color }}
      />
      <Handle
        type="target"
        id="outputs"
        position={Position.Right}
        style={{ background: color }}
      />
    </div>
  );
});
CustomNode.displayName = "CustomNode";
