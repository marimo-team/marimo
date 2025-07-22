/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React from "react";
import { useCellActions, useNotebook } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { useVariables } from "@/core/variables/state";
import { cn } from "@/utils/cn";
import {
  type CellGraph,
  cellGraphsAtom,
  isVariableAffectedBySelectedCell,
} from "./minimap-state";

interface MinimapCellProps {
  cellId: CellId;
  onClick: (cellId: CellId) => void;
  cellPositions: Readonly<Record<CellId, number>>;
}

const MinimapCell: React.FC<MinimapCellProps> = (props) => {
  const { cellId, onClick, cellPositions } = props;
  const notebook = useNotebook();
  const variables = useVariables();
  const selectedCellId = useLastFocusedCellId();
  const graphs = useAtomValue(cellGraphsAtom);

  const cell = notebook.cellData[cellId];
  const runtime = notebook.cellRuntime[cellId];

  const graph = graphs[cellId];
  const selectedGraph = selectedCellId ? graphs[selectedCellId] : undefined;

  const noneSelected = selectedCellId === undefined;
  const isSelected = selectedCellId === cellId;
  return (
    <button
      data-node-id={cellId}
      className={cn(
        "group bg-transparent text-left w-full flex relative justify-between items-center",
        "border-none rounded cursor-pointer",
        "h-[21px] pl-[51px] font-inherit",
        isSelected
          ? "text-primary-foreground"
          : runtime.errored
            ? "text-destructive"
            : "text-[var(--gray-8)] hover:text-[var(--gray-9)]",
      )}
      onClick={() => onClick(cellId)}
    >
      <div
        className={cn(
          "group-hover:bg-[var(--gray-3)] flex h-full w-full px-0.5 items-center rounded",
          isSelected && "bg-primary group-hover:bg-primary",
        )}
      >
        <div
          className="truncate px-1 font-mono text-sm flex gap-1"
          title={cell.code}
        >
          {graph.variables.length > 0 ? (
            graph.variables.map((varName, idx) => {
              const variable = variables[varName];
              return (
                <React.Fragment key={varName}>
                  {idx > 0 && ", "}
                  <span
                    className={cn({
                      "text-foreground": noneSelected,
                      "font-bold": isSelected,
                      "text-primary font-medium":
                        !isSelected &&
                        selectedCellId &&
                        selectedGraph &&
                        isVariableAffectedBySelectedCell(variable, {
                          selectedCellId,
                          selectedGraph,
                        }),
                    })}
                  >
                    {varName}
                  </span>
                </React.Fragment>
              );
            })
          ) : (
            <span className="overflow-hidden text-ellipsis whitespace-nowrap max-w-full">
              {codePreview(cell.code) ?? <span className="italic">empty</span>}
            </span>
          )}
        </div>
      </div>
      <svg
        className={cn(
          "absolute z-20 overflow-visible top-[10.5px] left-[calc(var(--spacing-extra-small,8px)_+_17px)]",
          noneSelected
            ? "text-foreground"
            : runtime.errored
              ? "text-destructive"
              : isSelected ||
                  selectedGraph?.parents.has(cellId) ||
                  selectedGraph?.children.has(cellId)
                ? "text-primary"
                : "text-[var(--gray-8)]",
        )}
      >
        {isSelected ? (
          <SelectedCell
            cellId={cellId}
            cellPositions={cellPositions}
            graph={graph}
          />
        ) : (
          <UnselectedCell
            cellId={cellId}
            graph={graph}
            selectedGraph={selectedGraph}
          />
        )}
      </svg>
    </button>
  );
};

export const Minimap: React.FC<{ className?: string }> = ({ className }) => {
  const notebook = useNotebook();
  const actions = useCellActions();
  const handleCellClick = (cellId: CellId) => {
    actions.focusCell({ cellId, where: "exact" });
  };
  const cellPositions: Record<CellId, number> = Object.fromEntries(
    notebook.cellIds.inOrderIds.map((id, idx) => [id, idx]),
  );
  return (
    <div
      className={cn(
        "fixed top-14 right-4 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 rounded-lg border shadow-lg w-64 contain-size h-3/4 flex flex-col",
        className,
      )}
    >
      <div className="flex items-center justify-between p-4 border-b">
        <span className="text-sm font-semibold">Minimap</span>
      </div>
      <div className="overflow-y-auto overflow-x-hidden py-3 pl-3 pr-4 flex-1 scrollbar-none">
        {notebook.cellIds.inOrderIds.map((cellId) => {
          return (
            <MinimapCell
              key={cellId}
              cellId={cellId}
              onClick={handleCellClick}
              cellPositions={cellPositions}
            />
          );
        })}
      </div>
    </div>
  );
};

function codePreview(code: string): string | undefined {
  return code.split("\n")[0].trim() || undefined;
}

// Connection paths (for selected)
const SelectedCell = (options: {
  cellId: CellId;
  cellPositions: Record<CellId, number>;
  graph: CellGraph;
}) => {
  const { cellId, cellPositions, graph } = options;
  const dy = 21;
  const paths: React.ReactElement[] = [];
  const currentY = cellPositions[cellId] ?? 0;

  // First, identify all cycles (nodes that are both parent and child)
  const cycles = new Set<CellId>();
  for (const parentCellId of graph.parents) {
    if (graph.children.has(parentCellId)) {
      cycles.add(parentCellId);
    }
  }

  // Add cycle paths first
  for (const cycleCellId of cycles) {
    const targetY = cellPositions[cycleCellId];
    if (targetY !== undefined) {
      const yDiff = (targetY - currentY) * dy;
      // Draw a rectangular path around both nodes to show the cycle
      paths.push(
        <path
          key={`${cellId}-cycle-${cycleCellId}`}
          d={`M -3 0 H -7 v ${yDiff} h 14 v ${-yDiff} H 3`}
          fill="none"
          strokeWidth="2"
          stroke="currentColor"
        />,
      );
    }
  }

  // Add regular upstream connections (excluding cycles)
  for (const parentCellId of graph.parents) {
    if (cycles.has(parentCellId)) {
      continue; // Skip - already handled as cycle
    }
    const targetY = cellPositions[parentCellId];
    if (targetY !== undefined) {
      const yDiff = (targetY - currentY) * dy;
      paths.push(
        <path
          key={`${cellId}-up-${parentCellId}`}
          d={`M -3 0 H -7 v ${yDiff} h -4`}
          fill="none"
          strokeWidth="2"
          stroke="currentColor"
        />,
      );
    }
  }

  // Add regular downstream connections (excluding cycles)
  for (const childCellId of graph.children) {
    if (cycles.has(childCellId)) {
      continue; // Skip - already handled as cycle
    }
    const targetY = cellPositions[childCellId];
    if (targetY !== undefined) {
      const yDiff = (targetY - currentY) * dy;
      paths.push(
        <path
          key={`${cellId}-down-${childCellId}`}
          d={`M 3 0 H 7 v ${yDiff} h 4`}
          fill="none"
          strokeWidth="2"
          stroke="currentColor"
        />,
      );
    }
  }

  return (
    <g transform="translate(0, 0)">
      <circle r={getCircleRadius(graph)} fill="currentColor" />
      <g className="pen">{paths}</g>
    </g>
  );
};

function isOrphan(graph: CellGraph): boolean {
  return graph.ancestors.size === 0 && graph.descendants.size === 0;
}

function getCircleRadius(graph: CellGraph): number {
  return isOrphan(graph) ? 1.5 : 3;
}

// Connection indicators for non-selected cells
function UnselectedCell(options: {
  cellId: CellId;
  graph: CellGraph;
  selectedGraph?: CellGraph;
}) {
  const { cellId, graph, selectedGraph } = options;
  const circleRadius = getCircleRadius(graph);

  const hasAncestors = graph.ancestors.size > 0;
  const hasDescendants = graph.descendants.size > 0;

  if (!selectedGraph) {
    // There is no selection, so show all upstream/downstream indicators
    return drawConnectionGlyph({
      circleRadius,
      leftWisker: hasAncestors,
      rightWisker: hasDescendants,
    });
  }

  const isAncestorOfSelected = selectedGraph.ancestors.has(cellId);
  const isDescendantOfSelected = selectedGraph.descendants.has(cellId);
  if (isAncestorOfSelected || isDescendantOfSelected) {
    return drawConnectionGlyph({
      circleRadius,
      leftWisker: hasAncestors,
      rightWisker: hasDescendants,
      // Node is a part of the current selection, need to jitter
      // If it's both ancestor and descendant (cycle), keep it centered
      shift:
        isAncestorOfSelected && isDescendantOfSelected
          ? undefined
          : isAncestorOfSelected
            ? "left"
            : "right",
    });
  }

  // Node is outside of the current selection (keep center & hide upstream/downstream indicators)
  return drawConnectionGlyph({
    circleRadius,
    leftWisker: false,
    rightWisker: false,
  });
}

function drawConnectionGlyph(options: {
  circleRadius: number;
  leftWisker: boolean;
  rightWisker: boolean;
  shift?: "left" | "right";
}) {
  const { circleRadius, leftWisker, rightWisker, shift } = options;
  const dx = shift === undefined ? 0 : shift === "left" ? -14 : 14;
  return (
    <g transform={`translate(${dx}, 0)`}>
      <g>
        {/* Whisker pointing left (has upstream connections) */}
        {leftWisker && (
          <path
            d="M 0 0 h -8"
            fill="none"
            strokeWidth="2"
            stroke="currentColor"
          />
        )}
        {/* Whisker pointing right (has downstream connections) */}
        {rightWisker && (
          <path
            d="M 0 0 h 8"
            fill="none"
            strokeWidth="2"
            stroke="currentColor"
          />
        )}
      </g>
      <circle r={circleRadius} fill="currentColor" />
    </g>
  );
}
