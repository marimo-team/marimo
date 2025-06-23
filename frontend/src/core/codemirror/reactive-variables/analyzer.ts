/* Copyright 2024 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";
import type { SyntaxNode, Tree } from "@lezer/common";
import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";

export interface ReactiveVariableRange {
  from: number;
  to: number;
  variableName: string;
}

/**
 * Analyzes the given editor state to find variable names that represent
 * reactive dependencies from other cells (similar to ObservableHQ's approach).
 */
export function findReactiveVariables(options: {
  state: EditorState;
  cellId: CellId;
  variables: Variables;
}): ReactiveVariableRange[] {
  const tree = syntaxTree(options.state);

  if (!tree) {
    // No AST available yet - this can happen during initial editor setup
    // or when the language parser hasn't processed the code
    return [];
  }

  // Don't highlight anything if there are syntax errors
  if (hasSyntaxErrors(tree)) {
    return [];
  }

  // Collect variable names that are:
  // - Not from in the current cell
  // - Not of type "module"
  const allVariableNames = new Set(
    Object.keys(options.variables).filter((name) => {
      const variable = options.variables[name as VariableName];
      return (
        variable.dataType !== "module" &&
        !variable.declaredBy.includes(options.cellId)
      );
    }),
  );

  if (allVariableNames.size === 0) {
    return [];
  }

  const ranges: ReactiveVariableRange[] = [];

  // Map from node position to declared variables in that scope
  const allDeclarations = new Map<number, Set<string>>();
  // Map from node position to scope type
  const scopeTypes = new Map<number, string>();

  // First pass: all variable declarations in their respective scopes
  function collectDeclarations(node: SyntaxNode | Tree, scopeStack: number[]) {
    const cursor = node.cursor();
    const nodeName = cursor.name;
    const nodeStart = cursor.from;

    const isNewScope = [
      "FunctionDefinition",
      "LambdaExpression",
      "ArrayComprehensionExpression",
      "SetComprehension",
      "DictionaryComprehensionExpression",
      "ComprehensionExpression",
      "ClassDefinition",
    ].includes(nodeName);

    let currentScopeStack = scopeStack;
    if (isNewScope) {
      currentScopeStack = [...scopeStack, nodeStart];
      allDeclarations.set(nodeStart, new Set());
      scopeTypes.set(nodeStart, nodeName);
    }

    switch (nodeName) {
      case "FunctionDefinition": {
        const subCursor = node.cursor();
        subCursor.firstChild();
        do {
          if (subCursor.name === "VariableName") {
            const functionName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add function name to the parent scope (not the function's own scope)
            const parentScope = scopeStack[scopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(parentScope)) {
              allDeclarations.set(parentScope, new Set());
            }
            allDeclarations.get(parentScope)?.add(functionName);
            break; // Function name is the first VariableName, so we can break here
          }
        } while (subCursor.nextSibling());

        // Function params
        const paramCursor = node.cursor();
        paramCursor.firstChild();
        do {
          if (paramCursor.name === "ParamList") {
            const paramListCursor = paramCursor.node.cursor();
            paramListCursor.firstChild();
            do {
              if (paramListCursor.name === "VariableName") {
                const paramName = options.state.doc.sliceString(
                  paramListCursor.from,
                  paramListCursor.to,
                );
                allDeclarations.get(nodeStart)?.add(paramName);
              }
            } while (paramListCursor.nextSibling());
          }
        } while (paramCursor.nextSibling());

        break;
      }
      case "LambdaExpression": {
        // Lambda params
        const subCursor = node.cursor();
        subCursor.firstChild();
        do {
          if (subCursor.name === "ParamList") {
            const paramCursor = subCursor.node.cursor();
            paramCursor.firstChild();
            do {
              if (paramCursor.name === "VariableName") {
                const paramName = options.state.doc.sliceString(
                  paramCursor.from,
                  paramCursor.to,
                );
                allDeclarations.get(nodeStart)?.add(paramName);
              }
            } while (paramCursor.nextSibling());
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "ArrayComprehensionExpression":
      case "DictionaryComprehensionExpression":
      case "SetComprehension":
      case "ComprehensionExpression": {
        // Domprehension variables - look for VariableName or TupleExpression after 'for'
        const subCursor = node.cursor();
        subCursor.firstChild();
        let foundFor = false;
        do {
          if (subCursor.name === "for") {
            foundFor = true;
          } else if (foundFor && subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            allDeclarations.get(nodeStart)?.add(varName);
          } else if (foundFor && subCursor.name === "TupleExpression") {
            // Handle tuple destructuring like (k, v)
            const tupleCursor = subCursor.node.cursor();
            tupleCursor.firstChild();
            do {
              if (tupleCursor.name === "VariableName") {
                const varName = options.state.doc.sliceString(
                  tupleCursor.from,
                  tupleCursor.to,
                );
                allDeclarations.get(nodeStart)?.add(varName);
              }
            } while (tupleCursor.nextSibling());
          } else if (foundFor && subCursor.name === "in") {
            foundFor = false; // Stop collecting variables after 'in'
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "ClassDefinition": {
        const subCursor = node.cursor();
        subCursor.firstChild();
        do {
          if (subCursor.name === "VariableName") {
            const className = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add class name to the parent scope (not the class's own scope)
            const parentScope = scopeStack[scopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(parentScope)) {
              allDeclarations.set(parentScope, new Set());
            }
            allDeclarations.get(parentScope)?.add(className);
            break; // Class name is the first VariableName, so we can break here
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "AssignStatement": {
        // Assignments - capture all variables being assigned to (variables that come before the last AssignOp)
        const subCursor = node.cursor();

        // First pass: all AssignOp positions to know where assignment targets end
        const assignOpPositions: number[] = [];
        subCursor.firstChild();
        do {
          if (subCursor.name === "AssignOp") {
            assignOpPositions.push(subCursor.from);
          }
        } while (subCursor.nextSibling());

        // Second pass: all VariableNames and TupleExpressions that come before the last AssignOp
        const lastAssignOpPosition =
          assignOpPositions[assignOpPositions.length - 1];

        // Helper function to extract variable names from assignment targets (including tuples)
        function extractAssignmentTargets(cursor: any, currentScope: number) {
          switch (cursor.name) {
            case "VariableName": {
              const varName = options.state.doc.sliceString(
                cursor.from,
                cursor.to,
              );
              // Check if we're in a class scope
              const isInClassScope =
                currentScope !== -1 &&
                scopeTypes.get(currentScope) === "ClassDefinition";

              if (!isInClassScope) {
                if (!allDeclarations.has(currentScope)) {
                  allDeclarations.set(currentScope, new Set());
                }
                allDeclarations.get(currentScope)?.add(varName);
              }

              break;
            }
            case "TupleExpression": {
              // Handle tuple unpacking like (x, (y, z)) = ...
              const tupleCursor = cursor.node.cursor();
              tupleCursor.firstChild();
              do {
                extractAssignmentTargets(tupleCursor, currentScope);
              } while (tupleCursor.nextSibling());

              break;
            }
            case "ArrayExpression": {
              // Handle list unpacking like [a, b, c] = ...
              const arrayCursor = cursor.node.cursor();
              arrayCursor.firstChild();
              do {
                extractAssignmentTargets(arrayCursor, currentScope);
              } while (arrayCursor.nextSibling());

              break;
            }
            // No default
          }
        }

        // Create a fresh cursor for the second pass
        const secondPassCursor = node.cursor();
        secondPassCursor.firstChild();
        const currentScope =
          currentScopeStack[currentScopeStack.length - 1] ?? -1;

        do {
          if (secondPassCursor.from < lastAssignOpPosition) {
            extractAssignmentTargets(secondPassCursor, currentScope);
          }
        } while (secondPassCursor.nextSibling());

        break;
      }
      case "ForStatement": {
        // For loop variables
        const subCursor = node.cursor();
        subCursor.firstChild();
        let foundFor = false;
        do {
          if (subCursor.name === "for") {
            foundFor = true;
          } else if (foundFor && subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add to the current innermost scope (or global if no scopes)
            const currentScope =
              currentScopeStack[currentScopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(currentScope)) {
              allDeclarations.set(currentScope, new Set());
            }
            allDeclarations.get(currentScope)?.add(varName);
          } else if (foundFor && subCursor.name === "in") {
            foundFor = false; // Stop collecting variables after 'in'
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "ImportStatement": {
        // Handle import x
        const subCursor = node.cursor();
        subCursor.firstChild();
        do {
          if (subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );

            const currentScope =
              currentScopeStack[currentScopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(currentScope)) {
              allDeclarations.set(currentScope, new Set());
            }
            allDeclarations.get(currentScope)?.add(varName);
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "ImportFromStatement": {
        // Handle from x import y as z
        const subCursor = node.cursor();
        subCursor.firstChild();
        let foundImport = false;
        do {
          if (subCursor.name === "import") {
            foundImport = true;
          } else if (foundImport && subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add to the current innermost scope
            const currentScope =
              currentScopeStack[currentScopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(currentScope)) {
              allDeclarations.set(currentScope, new Set());
            }
            allDeclarations.get(currentScope)?.add(varName);
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "TryStatement": {
        // Handle exception variable binding - look for 'as' followed by VariableName
        const subCursor = node.cursor();
        subCursor.firstChild();
        let foundAs = false;
        do {
          if (subCursor.name === "as") {
            foundAs = true;
          } else if (foundAs && subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add to the current innermost scope
            const currentScope =
              currentScopeStack[currentScopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(currentScope)) {
              allDeclarations.set(currentScope, new Set());
            }
            allDeclarations.get(currentScope)?.add(varName);
            foundAs = false;
          }
        } while (subCursor.nextSibling());

        break;
      }
      case "WithStatement": {
        // Handle with statement variable binding
        const subCursor = node.cursor();
        subCursor.firstChild();
        let foundAs = false;
        do {
          if (subCursor.name === "as") {
            foundAs = true;
          } else if (foundAs && subCursor.name === "VariableName") {
            const varName = options.state.doc.sliceString(
              subCursor.from,
              subCursor.to,
            );
            // Add to the current innermost scope
            const currentScope =
              currentScopeStack[currentScopeStack.length - 1] ?? -1;
            if (!allDeclarations.has(currentScope)) {
              allDeclarations.set(currentScope, new Set());
            }
            allDeclarations.get(currentScope)?.add(varName);
            foundAs = false;
          }
        } while (subCursor.nextSibling());

        break;
      }
      // No default
    }

    // Recursively process children
    if (cursor.firstChild()) {
      do {
        collectDeclarations(cursor.node, currentScopeStack);
      } while (cursor.nextSibling());
    }
  }

  // Second pass: find variable usages and check if they should be highlighted
  function findUsages(node: SyntaxNode | Tree, scopeStack: number[]) {
    const cursor = node.cursor();
    const nodeName = cursor.name;
    const nodeStart = cursor.from;

    // Check if this node creates a new scope
    const isNewScope = [
      "FunctionDefinition",
      "LambdaExpression",
      "ArrayComprehensionExpression",
      "SetComprehension",
      "DictionaryComprehensionExpression",
      "ComprehensionExpression",
      "ClassDefinition",
    ].includes(nodeName);

    let currentScopeStack = scopeStack;
    if (isNewScope) {
      currentScopeStack = [...scopeStack, nodeStart];
    }

    if (nodeName === "VariableName") {
      const varName = options.state.doc.sliceString(cursor.from, cursor.to);

      // Check if this variable should be highlighted
      if (allVariableNames.has(varName)) {
        // Check if it's declared in any enclosing scope
        let isDeclaredLocally = false;
        for (const scope of currentScopeStack) {
          if (allDeclarations.get(scope)?.has(varName)) {
            isDeclaredLocally = true;
            break;
          }
        }
        // Also check global scope
        if (allDeclarations.get(-1)?.has(varName)) {
          isDeclaredLocally = true;
        }

        if (!isDeclaredLocally) {
          ranges.push({
            from: cursor.from,
            to: cursor.to,
            variableName: varName,
          });
        }
      }
    }

    // Recursively process children
    if (cursor.firstChild()) {
      do {
        findUsages(cursor.node, currentScopeStack);
      } while (cursor.nextSibling());
    }
  }

  // Execute both passes
  collectDeclarations(tree, []);
  findUsages(tree, []);

  return ranges;
}

/**
 * Checks if the syntax tree contains any syntax errors.
 * If there are errors, we shouldn't show reactive variable highlighting.
 */
function hasSyntaxErrors(tree: Tree): boolean {
  const cursor = tree.cursor();
  do {
    // Lezer uses "⚠" as the error node name for syntax errors
    if (cursor.name === "⚠" || cursor.type.isError) {
      return true;
    }
  } while (cursor.next());
  return false;
}
