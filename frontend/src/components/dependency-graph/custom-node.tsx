/* Copyright 2023 Marimo. All rights reserved. */
import { CellData } from "@/core/model/cells";
import { TinyCode } from "@/editor/cell/TinyCode";
import { cn } from "@/lib/utils";
import { Atom, useAtomValue } from "jotai";
import { memo } from "react";
import { Handle, Position, NodeProps } from "reactflow";

export function getHeight(linesOfCode: number) {
  return Math.min(linesOfCode * 10 + 40, 200);
}

export const CustomNode = memo((props: NodeProps<{ atom: Atom<CellData> }>) => {
  const { data, selected, id } = props;
  const cell = useAtomValue(data.atom);
  const nonSelectedColor = "var(--gray7)";
  const selectedColor = "var(--gray10)";
  const color = selected ? selectedColor : nonSelectedColor;

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
          "flex flex-col bg-card border border-gray-200 rounded-md p-2 mx-[2px]",
          selected && "border-primary"
        )}
        style={{
          height: getHeight(linesOfCode),
          width: 150,
        }}
      >
        <div className="text-muted-foreground font-semibold text-xs pb-1">
          Cell {id}
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
