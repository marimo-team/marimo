/* Copyright 2026 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { SyntaxNode, Tree, TreeCursor } from "@lezer/common";

const SCOPE_CREATING_NODES = new Set([
  "FunctionDefinition",
  "LambdaExpression",
  "ArrayComprehensionExpression",
  "SetComprehension",
  "DictionaryComprehensionExpression",
  "ComprehensionExpression",
  "ClassDefinition",
]);

const POSITION_SENSITIVE_SCOPES = new Set(["ClassDefinition", "global"]);

interface ScopeContext {
  id: number;
  type: string;
}

interface VariableDeclaration {
  from: number;
  scopeId: number;
}

function goToPosition(view: EditorView, from: number): void {
  view.focus();
  // Wait for the next frame, otherwise codemirror will
  // add a cursor from a pointer click.
  requestAnimationFrame(() => {
    view.dispatch({
      selection: {
        anchor: from,
        head: from,
      },
      // Unfortunately, EditorView.scrollIntoView does
      // not support smooth scrolling.
      effects: EditorView.scrollIntoView(from, {
        y: "center",
      }),
    });
  });
}

function findFirstMatchingVariable(
  state: EditorState,
  variableName: string,
): number | null {
  const tree = syntaxTree(state);

  let from: number | null = null;

  tree.iterate({
    enter: (node) => {
      if (from !== null) {
        return false;
      }

      if (
        node.name === "VariableName" &&
        state.doc.sliceString(node.from, node.to) === variableName
      ) {
        from = node.from;
        return false;
      }

      if (node.name === "Comment" || node.name === "String") {
        return false;
      }

      return undefined;
    },
  });

  return from;
}

function getScopeChain(tree: Tree, usagePosition: number): ScopeContext[] {
  const scopeChain: ScopeContext[] = [];
  let currentNode: SyntaxNode | null = tree.resolveInner(usagePosition, 0);

  while (currentNode) {
    if (SCOPE_CREATING_NODES.has(currentNode.name)) {
      scopeChain.push({
        id: currentNode.from,
        type: currentNode.name,
      });
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

function collectMatchingTargets(
  cursor: TreeCursor,
  state: EditorState,
  variableName: string,
  scopeId: number,
  declarations: VariableDeclaration[],
) {
  switch (cursor.name) {
    case "VariableName":
      if (state.doc.sliceString(cursor.from, cursor.to) === variableName) {
        addDeclaration(declarations, scopeId, cursor.from);
      }
      break;

    case "TupleExpression":
    case "ArrayExpression": {
      const childCursor = cursor.node.cursor();
      childCursor.firstChild();
      do {
        collectMatchingTargets(
          childCursor,
          state,
          variableName,
          scopeId,
          declarations,
        );
      } while (childCursor.nextSibling());
      break;
    }
    default:
      break;
  }
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
      collectMatchingTargets(
        cursor,
        state,
        variableName,
        scopeId,
        declarations,
      );
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
  const currentScopeStack = isNewScope
    ? [...scopeStack, nodeStart]
    : scopeStack;
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
        collectFunctionParameters(
          node,
          state,
          variableName,
          nodeStart,
          declarations,
        );
      }
      break;
    }
    case "LambdaExpression":
      collectFunctionParameters(
        node,
        state,
        variableName,
        nodeStart,
        declarations,
      );
      break;

    case "ArrayComprehensionExpression":
    case "DictionaryComprehensionExpression":
    case "SetComprehension":
    case "ComprehensionExpression":
    case "ForStatement":
      collectForTargets(node, state, variableName, currentScope, declarations);
      break;

    case "AssignStatement": {
      const assignOpPositions: number[] = [];
      const subCursor = node.cursor();
      subCursor.firstChild();
      do {
        if (subCursor.name === "AssignOp") {
          assignOpPositions.push(subCursor.from);
        }
      } while (subCursor.nextSibling());

      const lastAssignOpPosition =
        assignOpPositions[assignOpPositions.length - 1];
      if (lastAssignOpPosition === undefined) {
        break;
      }

      const targetCursor = node.cursor();
      targetCursor.firstChild();
      do {
        if (targetCursor.from < lastAssignOpPosition) {
          collectMatchingTargets(
            targetCursor,
            state,
            variableName,
            currentScope,
            declarations,
          );
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
    case "TryStatement":
    case "WithStatement": {
      const subCursor = node.cursor();
      subCursor.firstChild();
      let foundAs = false;
      do {
        if (subCursor.name === "as") {
          foundAs = true;
        } else if (
          foundAs &&
          subCursor.name === "VariableName" &&
          state.doc.sliceString(subCursor.from, subCursor.to) === variableName
        ) {
          addDeclaration(declarations, currentScope, subCursor.from);
          foundAs = false;
        }
      } while (subCursor.nextSibling());
      break;
    }
    default:
      break;
  }

  traverseChildren(cursor, (childNode) => {
    collectMatchingDeclarations(
      childNode,
      state,
      variableName,
      currentScopeStack,
      declarations,
    );
  });
}

function findScopedDefinitionPosition(
  state: EditorState,
  variableName: string,
  usagePosition: number,
): number | null {
  const tree = syntaxTree(state);
  const declarations: VariableDeclaration[] = [];

  collectMatchingDeclarations(tree, state, variableName, [], declarations);

  const clampedUsagePosition = Math.max(
    0,
    Math.min(usagePosition, state.doc.length),
  );

  for (const scope of getScopeChain(tree, clampedUsagePosition)) {
    const match = declarations
      .filter((declaration) => declaration.scopeId === scope.id)
      .filter((declaration) => {
        return POSITION_SENSITIVE_SCOPES.has(scope.type)
          ? declaration.from <= clampedUsagePosition
          : true;
      })
      .toSorted((left, right) => left.from - right.from)[0];

    if (match) {
      return match.from;
    }
  }

  return null;
}

/**
 * This function will select the first occurrence of the given variable name,
 * for a given editor view.
 * @param view The editor view which contains the variable name.
 * @param variableName The name of the variable to select, if found in the editor.
 * @param usagePosition The position of the variable usage, if available.
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
      : null) ?? findFirstMatchingVariable(state, variableName);

  if (from === null) {
    return false;
  }

  goToPosition(view, from);
  return true;
}

/**
 * This function jumps to a given position in the editor.
 * @param view The editor view which contains the variable name.
 * @param lineNumber The line number to jump to.
 */
export function goToLine(view: EditorView, lineNumber: number): boolean {
  const line = view.state.doc.line(lineNumber);
  goToPosition(view, line.from);
  return true;
}
