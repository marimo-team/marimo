/* Copyright 2026 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import type { EditorState } from "@codemirror/state";
import { closeHoverTooltips, type EditorView } from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import { notebookAtom } from "../../cells/cells";
import { store } from "../../state/jotai";
import { getPositionAtWordBounds } from "../completion/hints";
import {
  findLastDefinition,
  findFirstMatchingVariable,
  findScopedDefinitionPosition,
  getDeclarations,
  goToPosition,
  goToVariableDefinition,
} from "./commands";

/**
 * CANONICAL SYMBOL TABLE (VERSIONED)
 */
interface SymbolEntry {
  cellId: CellId;
  definitions: number[]; // Ordered by AST position
}

interface SymbolTable {
  version: string; // Deterministic hash of cellIds + content
  index: Map<string, SymbolEntry[]>;
}

let CACHED_SYMBOL_TABLE: SymbolTable | null = null;

function isPrivateVariable(variableName: string) {
  return variableName.startsWith("_");
}

/**
 * DETERMINISTIC CELL ORDER: Flattened execution order from MultiColumn.
 */
function getDeterministicCellOrder(notebook: any): CellId[] {
  return notebook.cellIds.columns.flatMap((c: any) => c.inOrderIds);
}

/**
 * Structural fingerprint per cell.
 */
function computeCellHash(text: string): number {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = (hash << 5) - hash + text.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

function computeNotebookVersion(notebook: any, cellIds: CellId[]): string {
  return cellIds
    .map((id) => {
      const doc = notebook.cellHandles[id]?.current?.editorView?.state.doc;
      return `${id}:${computeCellHash(doc?.toString() ?? "")}`;
    })
    .join("|");
}

/**
 * BUILDER: AST-driven.
 */
function buildSymbolTable(notebook: any, variableName: string): SymbolTable {
  const cellIds = getDeterministicCellOrder(notebook);
  const version = computeNotebookVersion(notebook, cellIds);

  if (CACHED_SYMBOL_TABLE && CACHED_SYMBOL_TABLE.version === version) {
    if (CACHED_SYMBOL_TABLE.index.has(variableName)) {
      return CACHED_SYMBOL_TABLE;
    }
  } else {
    CACHED_SYMBOL_TABLE = { version, index: new Map() };
  }

  const entries: SymbolEntry[] = [];
  for (const cellId of cellIds) {
    const state = notebook.cellHandles[cellId]?.current?.editorView?.state;
    if (!state) {
      continue;
    }

    const declarations = getDeclarations(state, variableName);
    if (declarations.length > 0) {
      entries.push({
        cellId,
        definitions: declarations.map((d) => d.from).toSorted((a, b) => a - b),
      });
    }
  }

  CACHED_SYMBOL_TABLE.index.set(variableName, entries);
  return CACHED_SYMBOL_TABLE;
}

/**
 * PURE RESOLVER CONTRACT
 */
interface DefinitionTarget {
  cellId: CellId | null; // null means "current cell"
  position: number;
}

function resolveDefinition(
  symbolTable: SymbolTable,
  currentCellId: CellId | null,
  name: string,
  cellOrder: CellId[],
  usagePosition?: number,
  currentCellState?: EditorState,
): DefinitionTarget | null {
  // Phase 1: Scoped Binding (Hard Stop)
  if (usagePosition !== undefined && currentCellState) {
    const from = findScopedDefinitionPosition(
      currentCellState,
      name,
      usagePosition,
    );
    if (from !== null) {
      return { cellId: currentCellId, position: from };
    }
  }

  // Phase 2: Cross-Cell Symbol Lookup (Using deterministic order)
  if (!isPrivateVariable(name)) {
    const entries = symbolTable.index.get(name);
    if (entries && entries.length > 0) {
      const orderMap = new Map(cellOrder.map((id, i) => [id, i]));

      // Latest cell in canonical order first
      const sortedCells = [...entries].toSorted((a, b) => {
        const idxA = orderMap.get(a.cellId) ?? -1;
        const idxB = orderMap.get(b.cellId) ?? -1;
        return idxB - idxA;
      });

      const bestEntry = sortedCells[0];
      const bestPos = bestEntry.definitions[bestEntry.definitions.length - 1];

      return { cellId: bestEntry.cellId, position: bestPos };
    }
  }

  // Phase 3: Local AST Definition
  if (currentCellState) {
    const lastDef = findLastDefinition(currentCellState, name);
    if (lastDef !== null) {
      return { cellId: currentCellId, position: lastDef };
    }
  }

  // Phase 4: Lexical Fallback (VariableName nodes only)
  if (currentCellState) {
    const fallbackFrom = findFirstMatchingVariable(currentCellState, name);
    if (fallbackFrom !== null) {
      return { cellId: currentCellId, position: fallbackFrom };
    }
  }

  return null;
}

/**
 * ENTRY POINT UNIFICATION
 */
export function goToDefinitionAtCursorPosition(view: EditorView): boolean {
  const { state } = view;
  const { from } = state.selection.main;
  const wordBounds = getPositionAtWordBounds(state.doc, from);
  const word = state.doc.sliceString(
    wordBounds.startToken,
    wordBounds.endToken,
  );

  if (!word) {
    return false;
  }

  closeCompletion(view);
  view.dispatch({ effects: closeHoverTooltips });

  return goToDefinition(view, word, from);
}

export function goToDefinition(
  view: EditorView,
  variableName: string,
  usagePosition?: number,
): boolean {
  const notebook = store.get(notebookAtom);
  const cellOrder = getDeterministicCellOrder(notebook);
  const symbolTable = buildSymbolTable(notebook, variableName);

  // Find current cellId
  const currentCellId = Object.entries(notebook.cellHandles).find(
    ([_, handle]) => (handle as any).current?.editorView === view,
  )?.[0] as CellId;

  const result1 = resolveDefinition(
    symbolTable,
    currentCellId,
    variableName,
    cellOrder,
    usagePosition,
    view.state,
  );

  // Assertion Layer (Dev Mode)
  if (process.env.NODE_ENV === "development") {
    const result2 = resolveDefinition(
      symbolTable,
      currentCellId,
      variableName,
      cellOrder,
      usagePosition,
      view.state,
    );
    if (JSON.stringify(result1) !== JSON.stringify(result2)) {
      throw new Error(
        `[marimo] Nondeterministic navigation detected for "${variableName}"`,
      );
    }
  }

  if (!result1) {
    return false;
  }

  const targetView = result1.cellId
    ? notebook.cellHandles[result1.cellId]?.current?.editorView
    : view;

  if (targetView) {
    // If it's in the current view, we can use the optimized goToVariableDefinition
    if (targetView === view) {
      return goToVariableDefinition(view, variableName, usagePosition);
    }
    goToPosition(targetView, result1.position);
    return true;
  }

  return false;
}

export function goToCellLine(cellId: CellId, lineNumber: number): boolean {
  const notebook = store.get(notebookAtom);
  const view = notebook.cellHandles[cellId]?.current?.editorView;
  if (!view) {
    return false;
  }

  const line = view.state.doc.line(lineNumber);
  goToPosition(view, line.from);
  return true;
}
