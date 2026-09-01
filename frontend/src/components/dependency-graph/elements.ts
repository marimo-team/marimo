/* Copyright 2026 Marimo. All rights reserved. */

import type { Atom } from "jotai";
import { type Edge, MarkerType, type Node, type NodeProps } from "reactflow";
import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import type { Variable, VariableName, Variables } from "@/core/variables/types";
import { Arrays } from "@/utils/arrays";
import { extractCellPreview } from "./utils/cell-preview";

/** The edge type registered for dependency edges (see `custom-edge.tsx`). */
export const DEPENDENCY_EDGE_TYPE = "dependency";

export interface DependencyEdgeData {
  /** Variables carried across this edge. */
  variables: VariableName[];
  /** True when any carried variable is a mutable `State`/`SetFunctor` flow. */
  isStateFlow: boolean;
}

// A `State`/`SetFunctor` (from `mo.state`) is mutable mid-run, so it is drawn
// distinctly. `UIElement` is intentionally excluded: it is frontend-driven and
// immutable during a run.
const STATE_DATATYPES = new Set(["State", "SetFunctor"]);

export function isStateFlowVariable(variable: Variable): boolean {
  return variable.dataType != null && STATE_DATATYPES.has(variable.dataType);
}

export interface NodeData {
  atom: Atom<CellData>;
  /** Variables this cell defines — the node's primary identity when collapsed. */
  defs: VariableName[];
  /** When true the node renders its full code instead of the compact ref list. */
  expanded?: boolean;
}
export type CustomNodeProps = NodeProps<NodeData>;

const LINE_HEIGHT = 11; // matches TinyCode.css

export function getNodeHeight(linesOfCode: number) {
  return Math.min(linesOfCode * LINE_HEIGHT + 35, 200);
}

// Compact-node sizing. A collapsed node wraps its defined variables into
// comma-separated lines at a character budget, so it grows taller rather than
// wider; the same budget drives the estimated width so dagre and the DOM agree.
export const NODE_HEADER_HEIGHT = 22;
const DEF_LINE_HEIGHT = 16;
const BODY_V_PADDING = 10;
const EXPANDED_NODE_WIDTH = 300;
const CHAR_WIDTH = 6.5; // text-xs monospace-ish
const NODE_H_PADDING = 22;
const MIN_NODE_WIDTH = 90;
const MAX_NODE_WIDTH = 240;
// Wrap defs to the longest single name, but never narrower than this — short
// names pack several per line, a long one gets a line to itself.
const WRAP_MIN_CHARS = 12;

export function collapsedNodeWidth(label: string): number {
  const raw = label.length * CHAR_WIDTH + NODE_H_PADDING;
  return Math.min(Math.max(raw, MIN_NODE_WIDTH), MAX_NODE_WIDTH);
}

/** The per-line character budget used to wrap a node's defs. */
function defsWrapBudget(defs: VariableName[]): number {
  return defs.reduce((max, def) => Math.max(max, def.length), WRAP_MIN_CHARS);
}

/**
 * Greedily pack `defs` into comma-separated lines, each no wider than the
 * budget (the longest name, or `WRAP_MIN_CHARS`). No trailing commas.
 */
export function wrapDefs(defs: VariableName[]): string[] {
  const budget = defsWrapBudget(defs);
  const lines: string[] = [];
  let current = "";
  for (const def of defs) {
    if (current === "") {
      current = def;
    } else if (current.length + 2 + def.length <= budget) {
      current = `${current}, ${def}`;
    } else {
      lines.push(current);
      current = def;
    }
  }
  if (current !== "") {
    lines.push(current);
  }
  return lines;
}

/**
 * The lines shown in a collapsed node's body: its defs wrapped to a budget, or
 * a single code-preview line when the cell defines nothing.
 */
export function nodeBodyLines(data: NodeData): string[] {
  if (data.defs.length > 0) {
    return wrapDefs(data.defs);
  }
  const preview = extractCellPreview(store.get(data.atom).code).text;
  return preview ? [preview] : [];
}

export function nodeDimensions(data: NodeData): {
  width: number;
  height: number;
} {
  if (data.expanded) {
    const lines = store.get(data.atom).code.trim().split("\n").length;
    return { width: EXPANDED_NODE_WIDTH, height: getNodeHeight(lines) };
  }
  const lines = nodeBodyLines(data);
  const widthChars =
    data.defs.length > 0
      ? defsWrapBudget(data.defs)
      : lines.reduce((max, line) => Math.max(max, line.length), 0);
  const bodyLines = Math.max(lines.length, 1);
  return {
    width: collapsedNodeWidth("x".repeat(widthChars)),
    height: NODE_HEADER_HEIGHT + bodyLines * DEF_LINE_HEIGHT + BODY_V_PADDING,
  };
}

// The nodes must have the same handle IDs to ensure edges connect correctly
export const OUTPUTS_HANDLE_ID = "outputs";
export const INPUTS_HANDLE_ID = "inputs";

/**
 * Cells hidden by the reusable-functions filter: those the kernel marked as
 * valid top-level definitions (serialization hint `Valid`).
 */
export function reusableCellIds(
  cellIds: CellId[],
  cellRuntime: Record<CellId, CellRuntimeState>,
): Set<CellId> {
  const reusable = new Set<CellId>();
  for (const cellId of cellIds) {
    if (cellRuntime[cellId]?.serialization?.toLowerCase() === "valid") {
      reusable.add(cellId);
    }
  }
  return reusable;
}

/** Map each cell to the names of the variables it declares. */
export function computeDefsByCell(
  variables: Variables,
): Map<CellId, VariableName[]> {
  const defsByCell = new Map<CellId, VariableName[]>();
  for (const variable of Object.values(variables)) {
    for (const cellId of variable.declaredBy) {
      const defs = defsByCell.get(cellId) ?? [];
      defs.push(variable.name);
      defsByCell.set(cellId, defs);
    }
  }
  return defsByCell;
}

interface ElementsBuilder {
  createElements: (
    cellIds: CellId[],
    cellAtoms: Atom<CellData>[],
    variables: Variables,
    hidePureMarkdown: boolean,
    hideReusableFunctions: boolean,
  ) => { nodes: Node<NodeData>[]; edges: Edge[] };
}

export class VerticalElementsBuilder implements ElementsBuilder {
  private createEdge(source: CellId, target: CellId, direction: string): Edge {
    return {
      type: "smoothstep",
      pathOptions: {
        offset: 20,
        borderRadius: 100,
      },
      data: {
        direction: direction,
      },
      markerEnd: {
        type: MarkerType.Arrow,
      },
      id: `${source}-${target}-${direction}`,
      source: source,
      sourceHandle: direction,
      targetHandle: direction,
      target: target,
    };
  }

  private createNode(
    id: string,
    atom: Atom<CellData>,
    defs: VariableName[],
    prevY: number,
  ): Node<NodeData> {
    const data: NodeData = { atom, defs };
    const { width, height } = nodeDimensions(data);
    return {
      id: id,
      data,
      width,
      type: "custom",
      height,
      position: { x: 0, y: prevY + 20 },
    };
  }

  createElements(
    cellIds: CellId[],
    cellAtoms: Atom<CellData>[],
    variables: Variables,
    _hidePureMarkdown: boolean,
    _hideReusableFunctions: boolean,
  ) {
    let prevY = 0;
    const nodes: Node<NodeData>[] = [];
    const edges: Edge[] = [];
    const defsByCell = computeDefsByCell(variables);
    for (const [cellId, cellAtom] of Arrays.zip(cellIds, cellAtoms)) {
      const node = this.createNode(
        cellId,
        cellAtom,
        defsByCell.get(cellId) ?? [],
        prevY,
      );
      nodes.push(node);
      prevY = node.position.y + (node.height || 0);
    }

    const visited = new Set<string>();
    for (const variable of Object.values(variables)) {
      const { declaredBy, usedBy } = variable;
      for (const fromId of declaredBy) {
        for (const toId of usedBy) {
          const key = `${fromId}-${toId}`;
          if (visited.has(key)) {
            continue;
          }
          visited.add(key);
          edges.push(
            this.createEdge(fromId, toId, INPUTS_HANDLE_ID),
            this.createEdge(fromId, toId, OUTPUTS_HANDLE_ID),
          );
        }
      }
    }
    return { nodes, edges };
  }
}

interface AggregatedEdge {
  source: CellId;
  target: CellId;
  variables: VariableName[];
  isStateFlow: boolean;
}

export class TreeElementsBuilder implements ElementsBuilder {
  private createEdge(edge: AggregatedEdge): Edge<DependencyEdgeData> {
    const { source, target, variables, isStateFlow } = edge;
    return {
      type: DEPENDENCY_EDGE_TYPE,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isStateFlow ? "var(--amber-10)" : "var(--gray-8)",
      },
      id: `${source}-${target}`,
      data: { variables, isStateFlow },
      source: source,
      // Use the same handle ids as the custom node
      sourceHandle: OUTPUTS_HANDLE_ID,
      targetHandle: INPUTS_HANDLE_ID,
      target: target,
    };
  }

  private createNode(
    id: string,
    atom: Atom<CellData>,
    defs: VariableName[],
  ): Node<NodeData> {
    const data: NodeData = { atom, defs };
    const { width, height } = nodeDimensions(data);
    return {
      id: id,
      data,
      width,
      type: "custom",
      height,
      position: { x: 0, y: 0 },
    };
  }

  createElements(
    cellIds: CellId[],
    cellAtoms: Atom<CellData>[],
    variables: Variables,
    hidePureMarkdown: boolean,
    hideReusableFunctions: boolean,
  ) {
    const nodes: Node<NodeData>[] = [];

    const cellRuntime = getNotebook().cellRuntime;
    // Hidden reusable cells are dropped along with their edges — a reusable
    // function is nearly always referenced somewhere, so gating on "no edges"
    // would make the filter a no-op.
    const hiddenReusable = hideReusableFunctions
      ? reusableCellIds(cellIds, cellRuntime)
      : new Set<CellId>();

    const nodesWithEdges = new Set<CellId>();
    // Dedupe cell→cell edges, aggregating every variable that crosses them so a
    // single edge can carry multiple refs and flag whether any is a state flow.
    const edgesByPair = new Map<string, AggregatedEdge>();

    for (const variable of Object.values(variables)) {
      // Skip marimo, since likely every cell uses it
      if (variable.value === "marimo" && variable.name === "mo") {
        continue;
      }

      const isState = isStateFlowVariable(variable);
      const { declaredBy, usedBy } = variable;
      for (const fromId of declaredBy) {
        for (const toId of usedBy) {
          if (hiddenReusable.has(fromId) || hiddenReusable.has(toId)) {
            continue;
          }
          const key = `${fromId}-${toId}`;
          const existing = edgesByPair.get(key);
          if (existing) {
            existing.variables.push(variable.name);
            existing.isStateFlow ||= isState;
          } else {
            edgesByPair.set(key, {
              source: fromId,
              target: toId,
              variables: [variable.name],
              isStateFlow: isState,
            });
          }
          nodesWithEdges.add(fromId);
          nodesWithEdges.add(toId);
        }
      }
    }

    const edges = [...edgesByPair.values()].map((edge) =>
      this.createEdge(edge),
    );

    const defsByCell = computeDefsByCell(variables);

    for (const [cellId, cellAtom] of Arrays.zip(cellIds, cellAtoms)) {
      const code = store.get(cellAtom).code.trim();
      const hasEdge = nodesWithEdges.has(cellId);
      const isMarkdown = code.startsWith("mo.md");

      // Apply filters
      if (hidePureMarkdown && isMarkdown && !hasEdge) {
        continue;
      }
      if (hiddenReusable.has(cellId)) {
        continue;
      }

      // Show every cell that wasn't filtered out
      nodes.push(
        this.createNode(cellId, cellAtom, defsByCell.get(cellId) ?? []),
      );
    }

    return { nodes, edges };
  }
}
