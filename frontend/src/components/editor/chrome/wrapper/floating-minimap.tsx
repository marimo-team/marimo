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
        "bg-transparent text-left w-full flex relative justify-between items-center",
        "bg-white border-none rounded pr-0 cursor-pointer",
        "h-[21px] pl-[45px] font-inherit",
        "text-gray-400",
        {
          "text-red-400": runtime.errored,
          "text-white": isSelected,
        },
      )}
      onClick={() => onClick(cellId)}
    >
      <div
        className={cn(
          "flex h-full w-full px-1 items-center rounded",
          isSelected ? "bg-teal-700" : "bg-transparent",
        )}
      >
        <div
          className={cn(
            "truncate px-1 font-mono text-sm flex gap-1",
            isSelected ? "opacity-100" : "opacity-80",
          )}
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
                      "text-black": noneSelected,
                      "font-bold": isSelected,
                      "text-teal-800 font-medium":
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
              {codePreview(cell.code)}
            </span>
          )}
        </div>
      </div>
      <svg
        className={cn(
          "absolute z-20 overflow-visible top-[10.5px] left-[calc(var(--spacing-extra-small,8px)_+_17px)]",
          noneSelected
            ? "text-black"
            : runtime.errored
              ? "text-red-400"
              : isSelected ||
                  selectedGraph?.parents.has(cellId) ||
                  selectedGraph?.children.has(cellId)
                ? "text-teal-700"
                : "text-gray-400",
        )}
      >
        {isSelected ? (
          <g transform="translate(0, 0)">
            <circle r={getCircleRadius(graph)} fill="currentColor" />
            {renderConnections({ cellId, cellPositions, graph })}
          </g>
        ) : isOrphan(graph) ? (
          <g transform="translate(0, 0)">
            <circle r={getCircleRadius(graph)} fill="currentColor" />
          </g>
        ) : (
          renderConnectionForCell({ cellId, graph, selectedGraph })
        )}
      </svg>
    </button>
  );
};

export const FloatingMinimap: React.FC<{ className?: string }> = ({
  className,
}) => {
  const notebook = useNotebook();
  const actions = useCellActions();
  const handleCellClick = (cellId: CellId) => {
    actions.focusCell({ cellId, before: false });
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
      <div className="overflow-y-auto overflow-x-hidden pl-3 pr-4 flex-1 scrollbar-none">
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

function codePreview(code: string): string {
  return code.split("\n")[0].trim() || "-";
}

// Connection paths (for selected)
function renderConnections(options: {
  cellId: CellId;
  cellPositions: Record<CellId, number>;
  graph: CellGraph;
}) {
  const { cellId, cellPositions, graph } = options;
  const dy = 21;
  const paths: React.ReactElement[] = [];
  const currentY = cellPositions[cellId] ?? 0;

  // direct upstream (cells we depend on - to the left)
  for (const parentCellId of graph.parents) {
    const targetY = cellPositions[parentCellId];
    if (targetY !== undefined) {
      const yDiff = (targetY - currentY) * dy;
      paths.push(
        <path
          key={`up-${cellId}`}
          d={`M -3 0 H -7 v ${yDiff} h -4`}
          fill="none"
          strokeWidth="2"
          stroke="currentColor"
        />,
      );
    }
  }

  // direct downstream (cells that depend on us - to the right)
  for (const childCellId of graph.children) {
    const targetY = cellPositions[childCellId];
    if (targetY !== undefined) {
      const yDiff = (targetY - currentY) * dy;
      paths.push(
        <path
          key={`down-${childCellId}`}
          d={`M 3 0 H 7 v ${yDiff} h 4`}
          fill="none"
          strokeWidth="2"
          stroke="currentColor"
        />,
      );
    }
  }

  return <g className="pen">{paths}</g>;
}

function isOrphan(graph: CellGraph): boolean {
  return graph.ancestors.size === 0 && graph.descendants.size === 0;
}

function getCircleRadius(graph: CellGraph): number {
  return isOrphan(graph) ? 1.5 : 3;
}

// Connection indicators for non-selected cells
function renderConnectionForCell(options: {
  cellId: CellId;
  graph: CellGraph;
  selectedGraph?: CellGraph;
}) {
  const { cellId, graph, selectedGraph } = options;

  if (!selectedGraph) {
    // if nothing is selected draw the icon centers with
    // whiskers indicating any upstream/downstream deps
    return drawConnectionGlyph({
      leftWisker: graph.ancestors.size > 0,
      rightWisker: graph.descendants.size > 0,
      circleRadius: getCircleRadius(graph),
    });
  }

  const isAncestorOfSelected = selectedGraph.ancestors.has(cellId);
  const isDescendantOfSelected = selectedGraph.descendants.has(cellId);

  return drawConnectionGlyph({
    leftWisker: isDescendantOfSelected,
    rightWisker: isAncestorOfSelected,
    circleRadius: getCircleRadius(graph),
    shift: isAncestorOfSelected
      ? "left"
      : isDescendantOfSelected
        ? "right"
        : undefined,
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
