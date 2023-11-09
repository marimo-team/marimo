/* Copyright 2023 Marimo. All rights reserved. */
import { CellData } from "@/core/model/cells";
import { TinyCode } from "@/editor/cell/TinyCode";
import { cn } from "@/lib/utils";
import { Atom, useAtomValue } from "jotai";
import { memo } from "react";
import { Handle, Position, NodeProps, useStore } from "reactflow";

export function getHeight(linesOfCode: number) {
  return Math.min(linesOfCode * 10 + 40, 200);
}

function getWidth(canvasWidth: number) {
  const minWidth = 100;
  const maxWidth = 400;
  const padding = 50;
  return Math.min(Math.max(canvasWidth - padding * 2, minWidth), maxWidth);
}

export const CustomNode = memo((props: NodeProps<{ atom: Atom<CellData> }>) => {
  const { data, selected, id } = props;
  const cell = useAtomValue(data.atom);
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
          selected && "border-primary"
        )}
        style={{
          height: getHeight(linesOfCode),
          width: getWidth(reactFlowWidth),
        }}
      >
        <div className="text-muted-foreground font-semibold text-xs py-1 px-2 bg-muted border-b">
          Cell {id}
        </div>
        <div className="p-2">
          <TinyCode code={cell.code} />
        </div>
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
