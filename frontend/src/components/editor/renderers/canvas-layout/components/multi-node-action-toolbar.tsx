/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Multi-node action toolbar for canvas layout
 *
 * This component displays a floating toolbar when 2+ nodes are selected in the canvas.
 * It provides quick actions for the selected nodes.
 *
 * ## Architecture
 *
 * - `MultiNodeActionToolbar`: Main component that monitors node selection state
 * - `useMultiNodeActionButtons`: Hook that defines available actions and their handlers
 * - `MultiNodeActionButton`: Interface for action button configuration
 *
 * ## Adding New Actions
 *
 * To add new actions, edit the `useMultiNodeActionButtons` hook:
 *
 * 1. Add the action to the `actions` array for primary buttons (shown directly)
 * 2. Add the action to the `moreActions` array for secondary buttons (in dropdown)
 * 3. Actions are grouped in nested arrays - each group is separated by a visual divider
 *
 * Example:
 *
 * ```typescript
 * const actions: MultiNodeActionButton[][] = [
 *   [
 *     {
 *       icon: <Icon size={13} strokeWidth={1.5} />,
 *       label: "Action label",
 *       handle: (cellIds) => {
 *         // Implementation
 *       },
 *       hotkey: "cell.someAction", // Optional
 *       variant: "danger", // Optional, for destructive actions
 *       hidden: someCondition, // Optional, to conditionally show/hide
 *     },
 *   ],
 *   // Next group (separated by divider)
 *   [...],
 * ];
 * ```
 */

import { useNodes, useReactFlow } from "@xyflow/react";
import { useAtomValue } from "jotai";
import {
  AlertTriangleIcon,
  LayoutGridIcon,
  MoreHorizontalIcon,
  PlayIcon,
  Trash2Icon,
} from "lucide-react";
import React, { memo, useMemo } from "react";
import { FocusScope } from "react-aria";
import useEvent from "react-use-event-hook";
import type {
  LayoutDirection,
  LayoutRanker,
} from "@/components/dependency-graph/types";
import { useDeleteManyCellsCallback } from "@/components/editor/cell/useDeleteCell";
import { useRunCells } from "@/components/editor/cell/useRunCells";
import { MinimalShortcut } from "@/components/shortcuts/renderShortcut";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { hasOnlyOneCellAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { usePendingDeleteService } from "@/core/cells/pending-delete-service";
import { userConfigAtom } from "@/core/config/config";
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { useEventListener } from "@/hooks/useEventListener";
import { layoutElements } from "../layout";
import type { CanvasNode } from "../models";
import { resolveCollisions } from "../resolve-collisions";

interface MultiNodeActionButton {
  icon?: React.ReactNode;
  label: string;
  variant?: "danger";
  hidden?: boolean;
  handle: (cellIds: CellId[]) => void;
  hotkey?: HotkeyAction;
}

// Constants
const LAYOUT_ALGORITHMS_TOOLBAR: Array<{
  direction: LayoutDirection;
  ranker: LayoutRanker;
  label: string;
}> = [
  { direction: "TB", ranker: "longest-path", label: "Longest Path" },
  { direction: "TB", ranker: "network-simplex", label: "Network Simplex" },
  { direction: "TB", ranker: "tight-tree", label: "Tight Tree" },
] as const;

const LayoutDropdownComponent: React.FC<{
  cellIds: CellId[];
  onApplyLayout: (
    cellIds: CellId[],
    direction: LayoutDirection,
    ranker: LayoutRanker,
  ) => void;
  disabled?: boolean;
}> = ({ cellIds, onApplyLayout, disabled }) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 gap-1"
          title="Layout options"
          disabled={disabled}
        >
          <LayoutGridIcon size={13} strokeWidth={1.5} />
          <span className="text-xs">Layout</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" data-keep-node-selection={true}>
        {LAYOUT_ALGORITHMS_TOOLBAR.map((algorithm) => (
          <DropdownMenuItem
            key={algorithm.label}
            onSelect={() =>
              onApplyLayout(cellIds, algorithm.direction, algorithm.ranker)
            }
          >
            {algorithm.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const LayoutDropdown = memo(LayoutDropdownComponent);
LayoutDropdown.displayName = "LayoutDropdown";

const NodeStateDropdownComponent: React.FC<{
  actions: MultiNodeActionButton[][];
  cellIds: CellId[];
  disabled?: boolean;
}> = ({ actions, cellIds, disabled }) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 gap-1 select-none"
          title="More actions"
          disabled={disabled}
        >
          <MoreHorizontalIcon size={13} strokeWidth={1.5} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" data-keep-node-selection={true}>
        {actions.flatMap((group, index) => {
          const groupItems = group.map((action) => {
            return (
              <DropdownMenuItem
                key={action.label}
                onSelect={() => action.handle(cellIds)}
                className="flex items-center gap-2"
              >
                <div className="flex items-center flex-1">
                  {action.icon && (
                    <div className="mr-2 w-5 text-muted-foreground">
                      {action.icon}
                    </div>
                  )}
                  <div className="flex-1">{action.label}</div>
                  {action.hotkey && (
                    <MinimalShortcut
                      shortcut={action.hotkey}
                      className="ml-4"
                    />
                  )}
                </div>
              </DropdownMenuItem>
            );
          });
          return (
            <React.Fragment key={index}>
              {groupItems}
              {index < actions.length - 1 && <DropdownMenuSeparator />}
            </React.Fragment>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const NodeStateDropdown = memo(NodeStateDropdownComponent);
NodeStateDropdown.displayName = "NodeStateDropdown";

export function useMultiNodeActionButtons(cellIds: CellId[]) {
  const deleteCell = useDeleteManyCellsCallback();
  const hasOnlyOneCell = useAtomValue(hasOnlyOneCellAtom);
  const runCells = useRunCells();
  const pendingDeleteService = usePendingDeleteService();
  const userConfig = useAtomValue(userConfigAtom);
  const { setNodes, getNodes, getEdges } = useReactFlow();

  const selectedCount = cellIds.length;
  const canDelete = !hasOnlyOneCell || selectedCount < cellIds.length;

  const deleteSelectedNodes = useEvent((cellIds: CellId[]) => {
    // First click sets pending, second click deletes
    if (pendingDeleteService.idle && userConfig.keymap.destructive_delete) {
      pendingDeleteService.submit(cellIds);
      return;
    }
    deleteCell({ cellIds });
    pendingDeleteService.clear();
  });

  const layoutSelectedNodes = useEvent(
    (cellIds: CellId[], direction: LayoutDirection, ranker: LayoutRanker) => {
      const allNodes = getNodes() as CanvasNode[];
      const allEdges = getEdges();
      const selectedNodes = allNodes.filter((node) =>
        cellIds.includes(node.data.cellId),
      );

      if (selectedNodes.length < 2) {
        return;
      }

      // Get unselected nodes to use as boundaries
      const unselectedNodes = allNodes.filter(
        (node) => !cellIds.includes(node.data.cellId),
      );

      // Get edges that connect the selected nodes
      const selectedNodeIds = new Set(selectedNodes.map((n) => n.id));
      const relevantEdges = allEdges.filter(
        (edge) =>
          selectedNodeIds.has(edge.source) && selectedNodeIds.has(edge.target),
      );

      // Apply layout only to selected nodes, with unselected nodes as boundaries
      const { nodes: layoutedNodes } = layoutElements({
        nodes: selectedNodes as any,
        edges: relevantEdges as any,
        direction,
        ranker,
        boundaryNodes: unselectedNodes as any,
      });

      // Update nodes with new positions
      setNodes((currentNodes) =>
        currentNodes.map((node) => {
          const layoutedNode = layoutedNodes.find((n) => n.id === node.id);
          if (layoutedNode) {
            return {
              ...node,
              position: layoutedNode.position,
            };
          }
          return node;
        }),
      );

      // Apply collision resolution after layout
      // Non-selected nodes act as immovable boundaries
      setTimeout(() => {
        const selectedNodeIds = new Set(cellIds);
        setNodes((nds) =>
          resolveCollisions(nds, {
            maxIterations: 100,
            overlapThreshold: 0,
            margin: 20,
            edges: allEdges as any,
            selectedNodeIds,
          }),
        );
      }, 0);
    },
  );

  const runSelectedNodes = useEvent((cellIds: CellId[]) => {
    runCells(cellIds);
  });

  const actions: MultiNodeActionButton[][] = [
    [
      {
        icon: <Trash2Icon size={13} strokeWidth={1.5} />,
        label: "Delete",
        variant: "danger",
        hidden: !canDelete,
        handle: deleteSelectedNodes,
      },
    ],
    [
      {
        icon: <PlayIcon size={13} strokeWidth={1.5} />,
        label: "Run",
        handle: runSelectedNodes,
        hotkey: "cell.run",
      },
    ],
  ];

  const moreActions: MultiNodeActionButton[][] = [
    // Additional actions can be added here
  ];

  // Filter out hidden actions and empty groups
  return {
    actions: actions
      .map((group) => group.filter((action) => !action.hidden))
      .filter((group) => group.length > 0),
    moreActions: moreActions
      .map((group) => group.filter((action) => !action.hidden))
      .filter((group) => group.length > 0),
    layoutSelectedNodes,
  };
}

const MultiNodeActionToolbarComponent = () => {
  const nodes = useNodes<CanvasNode>();
  const selectedNodes = useMemo(
    () => nodes.filter((node) => node.selected),
    [nodes],
  );

  const cellIds = useMemo(
    () => selectedNodes.map((node) => node.data.cellId),
    [selectedNodes],
  );

  if (selectedNodes.length < 2) {
    return null;
  }

  return (
    <>
      <MultiNodeActionToolbarInternal cellIds={cellIds} />
      <MultiNodePendingDeleteBar cellIds={cellIds} />
    </>
  );
};

export const MultiNodeActionToolbar = memo(MultiNodeActionToolbarComponent);
MultiNodeActionToolbar.displayName = "MultiNodeActionToolbar";

const Separator = memo(() => <div className="h-4 w-px bg-border mx-1" />);
Separator.displayName = "Separator";

const MultiNodePendingDeleteBarComponent: React.FC<{ cellIds: CellId[] }> = ({
  cellIds,
}) => {
  const pendingDeleteService = usePendingDeleteService();
  const deleteCell = useDeleteManyCellsCallback();

  if (!pendingDeleteService.shouldConfirmDelete) {
    return null;
  }

  return (
    <div
      className="absolute bottom-12 justify-center flex w-full left-0 right-0 z-50 select-none"
      data-keep-node-selection={true}
    >
      <div className="mx-20">
        <div className="bg-(--amber-2) border border-(--amber-6) rounded-lg shadow-lg mt-14 px-4 py-3 animate-in slide-in-from-bottom-2 duration-200 select-none">
          <div className="flex items-start gap-3">
            <AlertTriangleIcon className="w-4 h-4 text-(--amber-11) mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-code text-sm text-[0.84375rem]">
                <p className="text-(--amber-11) font-medium">
                  Some nodes in selection may contain expensive operations.
                </p>
                <p className="text-(--amber-11) mt-1">
                  Are you sure you want to delete?
                </p>
              </div>
              <FocusScope restoreFocus={true} autoFocus={true}>
                <div
                  className="flex items-center gap-2 mt-3 select-none"
                  onKeyDown={(e) => {
                    // Stop propagation to prevent Cell's resumeCompletionHandler
                    e.stopPropagation();
                  }}
                >
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => pendingDeleteService.clear()}
                    className="text-(--amber-11) hover:bg-(--amber-4) hover:text-(--amber-11)"
                  >
                    Cancel
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => {
                      deleteCell({ cellIds });
                      pendingDeleteService.clear();
                    }}
                    className="bg-(--amber-11) hover:bg-(--amber-12) text-white border-(--amber-11)"
                  >
                    Delete
                  </Button>
                </div>
              </FocusScope>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const MultiNodePendingDeleteBar = memo(MultiNodePendingDeleteBarComponent);
MultiNodePendingDeleteBar.displayName = "MultiNodePendingDeleteBar";

const MultiNodeActionToolbarInternalComponent = ({
  cellIds,
}: {
  cellIds: CellId[];
}) => {
  const pendingDeleteService = usePendingDeleteService();
  const { actions, moreActions, layoutSelectedNodes } =
    useMultiNodeActionButtons(cellIds);

  const selectedCount = cellIds.length;

  // Clear selection when clicking outside
  const handleClearSelection = useEvent(() => {
    pendingDeleteService.clear();
  });

  useEventListener(window, "mousedown", (evt) => {
    // Clear selected, unless clicked inside an element that contains data-keep-node-selection
    if (
      (evt.target instanceof HTMLElement || evt.target instanceof SVGElement) &&
      (evt.target.closest("[data-keep-node-selection]") !== null ||
        evt.target.closest(".react-flow__node") !== null ||
        evt.target.closest(".react-flow__selectionpane") !== null)
    ) {
      return;
    }

    // HACK: evt.target is the root <html> element
    // when the DropdownMenu is closed.
    // This prevents the selection from being cleared when the opens/closes
    // the DropdownMenu.
    if (evt.target instanceof HTMLHtmlElement) {
      return;
    }
    handleClearSelection();
  });

  const isPendingDelete = !pendingDeleteService.idle;

  return (
    <div
      className="absolute bottom-12 justify-center flex w-full left-0 right-0 z-50 pointer-events-none"
      data-keep-node-selection={true}
    >
      <div className="bg-background/95 backdrop-blur-sm supports-backdrop-filter:bg-background/60 border border-(--slate-7) rounded-lg shadow-lg p-2 overflow-x-auto overflow-y-hidden mx-20 scrollbar-thin pointer-events-auto select-none">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-muted-foreground px-2 shrink-0 select-none">
            {selectedCount} nodes selected
          </span>
          <Separator />
          <LayoutDropdown
            cellIds={cellIds}
            onApplyLayout={layoutSelectedNodes}
            disabled={isPendingDelete}
          />
          <Separator />
          {actions.map((group, groupIndex) => (
            <div
              key={groupIndex}
              className="flex items-center gap-2 shrink-0 select-none"
            >
              {group.map((action) => (
                <Button
                  key={action.label}
                  variant={
                    action.variant === "danger" ? "linkDestructive" : "ghost"
                  }
                  size="sm"
                  onClick={() => action.handle(cellIds)}
                  className="h-8 px-2 gap-1 shrink-0 flex items-center select-none"
                  title={action.label}
                  disabled={isPendingDelete && action.label !== "Delete"}
                >
                  {action.icon}
                  <span className="text-xs">{action.label}</span>
                  {action.hotkey && (
                    <div className="ml-1 border bg-muted rounded-md px-1">
                      <MinimalShortcut shortcut={action.hotkey} />
                    </div>
                  )}
                </Button>
              ))}
              {groupIndex < actions.length - 1 && <Separator />}
            </div>
          ))}
          {moreActions.length > 0 && (
            <>
              <Separator />
              <NodeStateDropdown
                actions={moreActions}
                cellIds={cellIds}
                disabled={isPendingDelete}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const MultiNodeActionToolbarInternal = memo(
  MultiNodeActionToolbarInternalComponent,
);
MultiNodeActionToolbarInternal.displayName = "MultiNodeActionToolbarInternal";
