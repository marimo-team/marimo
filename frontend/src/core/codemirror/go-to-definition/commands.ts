/* Copyright 2026 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { SyntaxNode, Tree, TreeCursor } from "@lezer/common";

const SCOPE_CREATING_NODES = new Set([
  "FunctionDefinition",
  "LambdaExpression",
  "ArrayComprehensionExpression",
  "SetComprehensionExpression",
  "DictionaryComprehensionExpression",
  "ComprehensionExpression",
  "ClassDefinition",
]);

const POSITION_SENSITIVE_SCOPES = new Set(["ClassDefinition"]);

interface ScopeContext {
  id: number;
  type: string;
}

export interface VariableDeclaration {
  from: number;
  scopeId: number;
}

/**
 * UI SIDE-EFFECT: Moves the view to a specific position.
 * Guaranteed single point of UI mutation.
 */
export function goToPosition(view: EditorView, from: number): void {
  view.focus();
  requestAnimationFrame(() => {
    view.dispatch({
      selection: { anchor: from, head: from },
      effects: EditorView.scrollIntoView(from, { y: "center" }),
    });
  });
}

/**
 * PURE: Deterministic AST-node-filtered fallback.
 * Strictly matches VariableName nodes only.
 */
export function findFirstMatchingVariable(
  state: EditorState,
  variableName: string,
): number | null {
  const tree = syntaxTree(state);
  const candidates: number[] = [];

  tree.iterate({
    enter: (node) => {
      if (
        node.name === "VariableName" &&
        state.doc.sliceString(node.from, node.to) === variableName
      ) {
        candidates.push(node.from);
      }
      return undefined;
    },
  });

  if (candidates.length === 0) {return null;}
  // Deterministic tie-break: first in document order
  return candidates.toSorted((a, b) => a - b)[0];
}

function getScopeChain(tree: Tree, usagePosition: number): ScopeContext[] {
  const scopeChain: ScopeContext[] = [];
  let currentNode: SyntaxNode | null = tree.resolveInner(usagePosition, 0);

  while (currentNode) {
    if (SCOPE_CREATING_NODES.has(currentNode.name)) {
      const inFunctionLikeScope = scopeChain.some(
        (scope) =>
          scope.type === "FunctionDefinition" ||
          scope.type === "LambdaExpression",
      );
      if (!(inFunctionLikeScope && currentNode.name === "ClassDefinition")) {
        scopeChain.push({ id: currentNode.from, type: currentNode.name });
      }
    }
    currentNode = currentNode.parent;
  }

  scopeChain.push({ id: -1, type: "global" });
  return scopeChain;
}

function addDeclaration(
  declarations: VariableDeclaration[],
  scopeId: number,
  from: number,
) {
  declarations.push({ scopeId, from });
}

function traverseChildren(
  cursor: TreeCursor,
  callback: (node: SyntaxNode) => void,
) {
  if (cursor.firstChild()) {
    do {
      callback(cursor.node);
    } while (cursor.nextSibling());
  }
}

const DECLARATION_CACHE = new WeakMap<
  EditorState,
  Map<string, VariableDeclaration[]>
>();

/**
 * PURE: Extracts all valid declarations for a variable.
 */
export function getDeclarations(
  state: EditorState,
  variableName: string,
): VariableDeclaration[] {
  let stateCache = DECLARATION_CACHE.get(state);
  if (!stateCache) {
    stateCache = new Map();
    DECLARATION_CACHE.set(state, stateCache);
  }
  const cached = stateCache.get(variableName);
  if (cached) {return cached;}

  const declarations: VariableDeclaration[] = [];
  collectMatchingDeclarations(
    syntaxTree(state),
    state,
    variableName,
    [],
    declarations,
  );
  stateCache.set(variableName, declarations);
  return declarations;
}

function collectMatchingTargets(
  cursor: TreeCursor,
  state: EditorState,
  variableName: string,
  scopeId: number,
  declarations: VariableDeclaration[],
) {
  const tree = syntaxTree(state);
  const { from, to } = cursor;

  tree.iterate({
    from,
    to,
    enter: (node) => {
      if (
        node.name === "VariableName" &&
        state.doc.sliceString(node.from, node.to) === variableName
      ) {
        addDeclaration(declarations, scopeId, node.from);
      }
    },
  });
}

function collectFunctionParameters(
  node: SyntaxNode | Tree,
  state: EditorState,
  variableName: string,
  scopeId: number,
  declarations: VariableDeclaration[],
) {
  const cursor = node.cursor();
  cursor.firstChild();
  do {
    if (cursor.name !== "ParamList") {
      continue;
    }

    const paramCursor = cursor.node.cursor();
    paramCursor.firstChild();
    do {
      if (
        paramCursor.name === "VariableName" &&
        state.doc.sliceString(paramCursor.from, paramCursor.to) === variableName
      ) {
        addDeclaration(declarations, scopeId, paramCursor.from);
      }
    } while (paramCursor.nextSibling());
  } while (cursor.nextSibling());
}

function collectForTargets(
  node: SyntaxNode | Tree,
  state: EditorState,
  variableName: string,
  scopeId: number,
  declarations: VariableDeclaration[],
) {
  const cursor = node.cursor();
  cursor.firstChild();
  let foundFor = false;
  do {
    if (cursor.name === "for") {
      foundFor = true;
    } else if (foundFor && cursor.name === "in") {
      break;
    } else if (foundFor) {
      collectMatchingTargets(cursor, state, variableName, scopeId, declarations);
    }
  } while (cursor.nextSibling());
}

function collectMatchingDeclarations(
  node: SyntaxNode | Tree,
  state: EditorState,
  variableName: string,
  scopeStack: number[],
  declarations: VariableDeclaration[],
) {
  const cursor = node.cursor();
  const nodeName = cursor.name;
  const nodeStart = cursor.from;

  const isNewScope = SCOPE_CREATING_NODES.has(nodeName);
  const currentScopeStack = isNewScope ? [...scopeStack, nodeStart] : scopeStack;
  const currentScope = currentScopeStack[currentScopeStack.length - 1] ?? -1;

  switch (nodeName) {
    case "FunctionDefinition":
    case "ClassDefinition": {
      const subCursor = node.cursor();
      subCursor.firstChild();
      do {
        if (
          subCursor.name === "VariableName" &&
          state.doc.sliceString(subCursor.from, subCursor.to) === variableName
        ) {
          const parentScope = scopeStack[scopeStack.length - 1] ?? -1;
          addDeclaration(declarations, parentScope, subCursor.from);
          break;
        }
      } while (subCursor.nextSibling());

      if (nodeName === "FunctionDefinition") {
        collectFunctionParameters(node, state, variableName, nodeStart, declarations);
      }
      break;
    }
    case "LambdaExpression":
      collectFunctionParameters(node, state, variableName, nodeStart, declarations);
      break;

    case "ArrayComprehensionExpression":
    case "DictionaryComprehensionExpression":
    case "SetComprehensionExpression":
    case "ComprehensionExpression":
    case "ForStatement":
      collectForTargets(node, state, variableName, currentScope, declarations);
      break;

    case "AssignStatement": {
      const assignOpPositions: number[] = [];
      const subCursor = node.cursor();
      subCursor.firstChild();
      do {
        if (subCursor.name === "AssignOp") {assignOpPositions.push(subCursor.from);}
      } while (subCursor.nextSibling());

      const lastAssignOpPosition = assignOpPositions[assignOpPositions.length - 1];
      if (lastAssignOpPosition === undefined) {break;}

      const targetCursor = node.cursor();
      targetCursor.firstChild();
      do {
        if (targetCursor.from < lastAssignOpPosition) {
          collectMatchingTargets(targetCursor, state, variableName, currentScope, declarations);
        }
      } while (targetCursor.nextSibling());
      break;
    }
    case "ImportStatement": {
      const subCursor = node.cursor();
      subCursor.firstChild();
      do {
        if (
          subCursor.name === "VariableName" &&
          state.doc.sliceString(subCursor.from, subCursor.to) === variableName
        ) {
          addDeclaration(declarations, currentScope, subCursor.from);
        }
      } while (subCursor.nextSibling());
      break;
    }
    case "ImportFromStatement": {
      const subCursor = node.cursor();
      subCursor.firstChild();
      let foundImport = false;
      do {
        if (subCursor.name === "import") {
          foundImport = true;
        } else if (
          foundImport &&
          subCursor.name === "VariableName" &&
          state.doc.sliceString(subCursor.from, subCursor.to) === variableName
        ) {
          addDeclaration(declarations, currentScope, subCursor.from);
        }
      } while (subCursor.nextSibling());
      break;
    }
    default:
      break;
  }

  traverseChildren(cursor, (childNode) => {
    collectMatchingDeclarations(childNode, state, variableName, currentScopeStack, declarations);
  });
}

/**
 * PURE: Scoped binding resolution with shadowing.
 * Guaranteed order-independent collection.
 */
export function findScopedDefinitionPosition(
  state: EditorState,
  variableName: string,
  usagePosition: number,
): number | null {
  const tree = syntaxTree(state);
  const declarations = getDeclarations(state, variableName);
  const clampedUsagePosition = Math.max(0, Math.min(usagePosition, state.doc.length));

  for (const scope of getScopeChain(tree, clampedUsagePosition)) {
    const scopeCandidates = declarations
      .filter((d) => d.scopeId === scope.id)
      .filter((d) => (POSITION_SENSITIVE_SCOPES.has(scope.type) ? d.from <= clampedUsagePosition : true));

    if (scopeCandidates.length > 0) {
      // Deterministic rule: LAST assignment in scope wins
      return scopeCandidates.toSorted((a, b) => b.from - a.from)[0].from;
    }
  }
  return null;
}

/**
 * PURE: Deterministic LAST syntactic definition in document order.
 */
export function findLastDefinition(
  state: EditorState,
  variableName: string,
): number | null {
  const declarations = getDeclarations(state, variableName);
  if (declarations.length === 0) {return null;}
  return declarations.toSorted((a, b) => a.from - b.from)[0].from;
}

/**
 * This function will select the first occurrence of the given variable name,
 * for a given editor view.
 */
export function goToVariableDefinition(
  view: EditorView,
  variableName: string,
  usagePosition?: number,
): boolean {
  const { state } = view;
  const from =
    (usagePosition !== undefined
      ? findScopedDefinitionPosition(state, variableName, usagePosition)
      : null) ??
    findLastDefinition(state, variableName) ??
    findFirstMatchingVariable(state, variableName);

  if (from === null) {
    return false;
  }

  goToPosition(view, from);
  return true;
}

/**
 * This function jumps to a given position in the editor.
 */
export function goToLine(view: EditorView, lineNumber: number): boolean {
  const line = view.state.doc.line(lineNumber);
  goToPosition(view, line.from);
  return true;
}
