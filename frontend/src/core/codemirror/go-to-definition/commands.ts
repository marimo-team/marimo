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

interface VariableDeclaration {
  from: number;
  scopeId: number;
}

function goToPosition(view: EditorView, from: number): void {
  // Focus on the next frame: a synchronous focus is a no-op while a Radix
  // context menu still owns focus, and codemirror would otherwise add a
  // cursor from the pointer click.
  requestAnimationFrame(() => {
    view.focus();
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
      // Skip ClassDefinition if we've already seen a function/lambda.
      const inFunctionLikeScope = scopeChain.some(
        (scope) =>
          scope.type === "FunctionDefinition" ||
          scope.type === "LambdaExpression",
      );
      if (!(inFunctionLikeScope && currentNode.name === "ClassDefinition")) {
        scopeChain.push({
          id: currentNode.from,
          type: currentNode.name,
        });
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
      // The grammar emits one ImportStatement for both `import x [as y]` and
      // `from m import x [as y], ...`. Direct children include the keywords
      // (`from`/`import`/`as`), commas, dots, and every VariableName from the
      // module path AND the import list. We only want the names that actually
      // bind in the current scope: the post-`as` alias if present, otherwise
      // the imported name itself. Names before `import` (the from-path) and
      // the original name when an alias follows it are NOT bindings.
      const subCursor = node.cursor();
      subCursor.firstChild();
      let pastImport = false;
      // Buffer the most recent post-`import` VariableName so we can defer
      // committing it until we know whether `as` follows.
      let pending: { from: number; matches: boolean } | null = null;
      const commit = () => {
        if (pending?.matches) {
          addDeclaration(declarations, currentScope, pending.from);
        }
        pending = null;
      };
      do {
        if (subCursor.name === "import") {
          pastImport = true;
          continue;
        }
        if (!pastImport) {
          continue;
        }
        if (subCursor.name === "as") {
          // Next VariableName is the alias and replaces `pending`.
          pending = null;
          continue;
        }
        if (subCursor.name === "VariableName") {
          // Flush any previous pending name (no `as` followed it).
          commit();
          pending = {
            from: subCursor.from,
            matches:
              state.doc.sliceString(subCursor.from, subCursor.to) ===
              variableName,
          };
        } else if (subCursor.name === ",") {
          commit();
        }
      } while (subCursor.nextSibling());
      commit();
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
 * This function selects a scoped definition for the given variable name, when
 * a usage position is available, or optionally falls back to the first matching
 * variable name in the given editor view.
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
  // When the caller knows the usage position, trust the scoped lookup. Falling
  // back to first-match would defeat the local-vs-cross-cell decision in
  // goToDefinition: if the symbol only appears as a module path in an import,
  // scoped resolution returns null and we want the caller to try other cells.
  const from =
    usagePosition !== undefined
      ? findScopedDefinitionPosition(state, variableName, usagePosition)
      : findFirstMatchingVariable(state, variableName);

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
