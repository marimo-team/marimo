/* Copyright 2024 Marimo. All rights reserved. */

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Node,
  type NodeTypes,
  type OnNodesChange,
  PanOnScrollMode,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import { useAtomValue } from "jotai";
import React, { memo, useEffect, useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import "@xyflow/react/dist/style.css";
import "./canvas.css";
import type {
  LayoutDirection,
  LayoutRanker,
} from "@/components/dependency-graph/types";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CellId } from "@/core/cells/ids";
import type { ICellRendererProps } from "../../types";
import {
  useCanvasHotkeys,
  useNewCellPositioning,
  useVariablesForEdges,
} from "../hooks";
import { layoutElements } from "../layout";
import type { CanvasEdge } from "../models";
import { resolveCollisions } from "../resolve-collisions";
import { canvasSettingsAtom } from "../state";
import type { CanvasLayout } from "../types";
import { layoutToNodes, nodesToLayout } from "../utils";
import { AddCellMenuItems } from "./add-cell-menu-items";
import { AIPromptBar } from "./ai-prompt-bar";
import { CanvasControls } from "./controls";
import { LayoutActions } from "./layout-actions";
import { MultiNodeActionToolbar } from "./multi-node-action-toolbar";
import { CellNode } from "./node";

// Constants
const STARTUP_COLLISION_CONFIG = {
  maxIterations: 100,
  overlapThreshold: 0,
  margin: 20,
} as const;

const DRAG_STOP_COLLISION_CONFIG = {
  maxIterations: 1000,
  overlapThreshold: 0.5,
  margin: 15,
} as const;

const REACT_FLOW_CONSTANTS = {
  nodesConnectable: false,
  panOnScroll: true,
  zoomOnScroll: true,
  panOnScrollMode: PanOnScrollMode.Free,
  minZoom: 0.1,
  maxZoom: 2,
  defaultEdgeOptions: {
    type: "smoothstep" as const,
  },
} as const;

const BACKGROUND_CONFIG = {
  variant: BackgroundVariant.Dots,
  bgColor: "#f1f1f1",
  size: 1,
} as const;

const MINIMAP_CONFIG = {
  selectedColor: "#3b82f6",
  defaultColor: "#e5e7eb",
  maskColor: "rgba(0, 0, 0, 0.1)",
} as const;

const DELETE_KEY_CODES: ["Backspace", "Delete"] = ["Backspace", "Delete"];

// Utility functions
const getMinimapNodeColor = (node: { selected?: boolean }) => {
  return node.selected
    ? MINIMAP_CONFIG.selectedColor
    : MINIMAP_CONFIG.defaultColor;
};

const getCursorClass = (interactionMode: "hand" | "pointer") => {
  return interactionMode === "hand"
    ? "canvas-hand-mode"
    : "canvas-pointer-mode";
};

/**
 * Main canvas component using react-flow
 */
const CanvasComponent: React.FC<ICellRendererProps<CanvasLayout>> = ({
  cells,
  layout,
  setLayout,
  mode,
  appConfig,
}) => {
  const settings = useAtomValue(canvasSettingsAtom);
  const isEditable = mode === "edit";
  const deleteCell = useDeleteCellCallback();
  const { screenToFlowPosition } = useReactFlow();

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    flowX: number;
    flowY: number;
  } | null>(null);

  // Convert layout to nodes
  const initialNodes = useMemo(() => layoutToNodes(layout), [layout]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);

  // Register canvas hotkeys (select all, clear selection, etc.)
  useCanvasHotkeys(isEditable);

  // Get edges from variable dependencies
  const variableEdges = useVariablesForEdges();
  const [edges, setEdges, onEdgesChange] =
    useEdgesState<CanvasEdge>(variableEdges);

  // Update edges when variables change
  useEffect(() => {
    setEdges(variableEdges);
  }, [variableEdges, setEdges]);

  // Sync nodes when cells are added/deleted externally (undo, imports, etc.)
  useEffect(() => {
    const cellIds = new Set(cells.map((c) => c.id));
    const layoutCellMap = new Map(layout.cells.map((c) => [c.i, c]));

    setNodes((currentNodes) => {
      const nodeCellIds = new Set(
        currentNodes.map((n) => n.data.cellId as CellId),
      );

      // Check for removed cells
      const hasRemovedCells = currentNodes.some(
        (node) => !cellIds.has(node.data.cellId as CellId),
      );

      // Check for added cells
      const addedCellIds = Array.from(cellIds).filter(
        (cellId) => !nodeCellIds.has(cellId),
      );

      // If no changes, return current nodes to avoid re-render
      if (!hasRemovedCells && addedCellIds.length === 0) {
        return currentNodes;
      }

      // Start with filtered nodes (remove deleted cells)
      let updatedNodes = hasRemovedCells
        ? currentNodes.filter((node) => cellIds.has(node.data.cellId as CellId))
        : currentNodes;

      // Add new nodes for added cells
      if (addedCellIds.length > 0) {
        const newNodes = addedCellIds
          .map((cellId) => {
            const layoutCell = layoutCellMap.get(cellId);
            if (!layoutCell) {
              return null;
            }

            // Create node from layout cell
            return {
              id: cellId,
              type: "cell" as const,
              position: { x: layoutCell.x, y: layoutCell.y },
              data: {
                cellId,
              },
              width: layoutCell.w,
              height: layoutCell.h,
            };
          })
          .filter((node): node is NonNullable<typeof node> => node !== null);

        updatedNodes = [...updatedNodes, ...newNodes];
      }

      return updatedNodes;
    });
  }, [cells, layout.cells, setNodes]);

  // Apply collision resolution on startup
  useEffect(() => {
    setNodes((nds) => resolveCollisions(nds, STARTUP_COLLISION_CONFIG));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle positioning of newly added cells
  useNewCellPositioning({ cells, nodes, setNodes });

  // Custom node types
  const nodeTypes: NodeTypes = useMemo(
    () => ({
      cell: (props) => (
        <CellNode
          {...props}
          appConfig={appConfig}
          isEditable={isEditable}
          dataFlow={settings.dataFlow}
        />
      ),
    }),
    [appConfig, isEditable, settings.dataFlow],
  );

  // Handle nodes change and update layout
  const handleNodesChange: OnNodesChange = useEvent((changes) => {
    onNodesChange(changes);

    // Update layout after nodes change
    setNodes((currentNodes) => {
      const newLayout = nodesToLayout(currentNodes as Node[], {
        width: layout.width,
        height: layout.height,
        showGrid: layout.showGrid,
        gridSize: layout.gridSize,
      });
      setLayout(newLayout);
      return currentNodes;
    });
  });

  // Handle node deletion
  const handleNodesDelete = useEvent((nodesToDelete: Node[]) => {
    for (const node of nodesToDelete) {
      deleteCell({ cellId: node.id as CellId });
    }
  });

  // Handle layout application
  const applyLayout = useEvent(
    (direction: LayoutDirection, ranker: LayoutRanker) => {
      const { nodes: layoutedNodes } = layoutElements({
        nodes: nodes as any,
        edges: edges as any,
        direction,
        ranker,
      });
      // Update nodes with new positions from the layout
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

      // Apply collision resolution after layout to prevent overlaps
      setTimeout(() => {
        setNodes((nds) =>
          resolveCollisions(nds, {
            maxIterations: 100,
            overlapThreshold: 0,
            margin: 20,
            edges: edges as any,
          }),
        );
      }, 0);
    },
  );

  // Handle deleting empty cells
  const deleteEmptyCells = useEvent(() => {
    const emptyCellIds = cells
      .filter((cell) => cell.code.trim() === "")
      .map((cell) => cell.id);

    for (const cellId of emptyCellIds) {
      deleteCell({ cellId });
    }
  });

  // Handle node drag stop - resolve collisions
  const onNodeDragStop = useEvent(() => {
    setNodes((nds) => {
      // Get selected node IDs for selection-aware collision
      const selectedNodeIds = new Set(
        nds.filter((node) => node.selected).map((node) => node.id),
      );

      return resolveCollisions(nds, {
        ...DRAG_STOP_COLLISION_CONFIG,
        selectedNodeIds,
        gridSize: settings.snapToGrid ? settings.gridSize : undefined,
        edges: edges as any,
      });
    });
  });

  // Handle right-click on canvas
  const onPaneContextMenu = useEvent(
    (event: MouseEvent | React.MouseEvent<Element, MouseEvent>) => {
      if (!isEditable) {
        return;
      }
      event.preventDefault();

      // Convert screen coordinates to flow coordinates
      const flowPosition = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        flowX: flowPosition.x,
        flowY: flowPosition.y,
      });
    },
  );

  // Determine pan behavior based on interaction mode
  const panOnDrag = settings.interactionMode === "hand";
  const selectionOnDrag = settings.interactionMode === "pointer" && isEditable;

  // CSS class for cursor styling
  const cursorClass = useMemo(
    () => getCursorClass(settings.interactionMode),
    [settings.interactionMode],
  );

  return (
    <div className={`w-full h-full relative ${cursorClass}`}>
      {isEditable && <AIPromptBar />}
      {isEditable && <MultiNodeActionToolbar />}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onNodesDelete={handleNodesDelete}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onPaneContextMenu={onPaneContextMenu}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid={settings.snapToGrid}
        snapGrid={[settings.gridSize, settings.gridSize]}
        nodesDraggable={isEditable}
        nodesConnectable={REACT_FLOW_CONSTANTS.nodesConnectable}
        elementsSelectable={isEditable}
        panOnDrag={panOnDrag}
        selectionOnDrag={selectionOnDrag}
        panOnScroll={REACT_FLOW_CONSTANTS.panOnScroll}
        zoomOnScroll={REACT_FLOW_CONSTANTS.zoomOnScroll}
        preventScrolling={isEditable}
        panOnScrollMode={REACT_FLOW_CONSTANTS.panOnScrollMode}
        minZoom={REACT_FLOW_CONSTANTS.minZoom}
        maxZoom={REACT_FLOW_CONSTANTS.maxZoom}
        deleteKeyCode={isEditable ? DELETE_KEY_CODES : null}
        defaultEdgeOptions={REACT_FLOW_CONSTANTS.defaultEdgeOptions}
      >
        {/* Background */}
        <Background
          variant={BACKGROUND_CONFIG.variant}
          gap={settings.gridSize}
          bgColor={BACKGROUND_CONFIG.bgColor}
          size={BACKGROUND_CONFIG.size}
        />

        {/* Controls */}
        <Controls>
          {isEditable && <CanvasControls />}
          <LayoutActions
            onApplyLayout={applyLayout}
            onDeleteEmptyCells={deleteEmptyCells}
          />
        </Controls>

        {/* Minimap */}
        {settings.showMinimap && (
          <MiniMap
            nodeColor={getMinimapNodeColor}
            maskColor={MINIMAP_CONFIG.maskColor}
          />
        )}
      </ReactFlow>

      {/* Context menu for adding cells on canvas right-click */}
      {isEditable && contextMenu && (
        <DropdownMenu
          open={!!contextMenu}
          onOpenChange={(open) => {
            if (!open) {
              setContextMenu(null);
            }
          }}
        >
          <DropdownMenuTrigger asChild>
            <div
              style={{
                position: "fixed",
                left: contextMenu.x,
                top: contextMenu.y,
                width: 0,
                height: 0,
              }}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <AddCellMenuItems
              direction="below"
              cellId={null as any}
              nodePosition={{ x: contextMenu.flowX, y: contextMenu.flowY }}
              nodeSize={{ width: 0, height: 0 }}
            />
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
};

export const Canvas = memo(CanvasComponent);
Canvas.displayName = "Canvas";
