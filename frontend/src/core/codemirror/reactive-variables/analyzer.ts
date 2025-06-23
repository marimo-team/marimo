/* Copyright 2024 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";

import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";

export interface ReactiveVariableRange {
  from: number;
  to: number;
  variableName: string;
}

interface Scope {
  type: "function" | "lambda" | "comprehension";
  start: number;
  end: number;
  parameters: Set<string>; // Parameter names that shadow globals in this scope
  localDeclarations: Set<string>; // Local variable declarations within this scope
}

/**
 * Analyzes the given editor state to find variable names that represent
 * reactive dependencies from other cells (similar to ObservableHQ's approach).
 *
 * A variable is considered reactive if:
 * - It's used in the current cell
 * - It's declared by a different cell (not the current one)
 * - It's not shadowed by a local parameter in the current scope
 */
export function findReactiveVariables(options: {
  state: EditorState;
  cellId: CellId;
  variables: Variables;
}): ReactiveVariableRange[] {
  const tree = syntaxTree(options.state);
  const ranges: ReactiveVariableRange[] = [];

  if (!tree) {
    // No AST available yet - this can happen during initial editor setup
    // or when the language parser hasn't processed the code
    return ranges;
  }

  // Don't highlight anything if there are syntax errors
  if (hasSyntaxErrors(tree)) {
    return ranges;
  }

  // First pass: build scopes with their parameters
  const scopes = buildScopes(tree, options.state.doc.toString());

  // Second pass: find reactive variables, checking for shadowing
  const cursor = tree.cursor();

  do {
    if (cursor.name === "VariableName") {
      const { from, to } = cursor;
      const variableName = options.state.doc.sliceString(
        from,
        to,
      ) as VariableName;

      // Check if this variable is shadowed by a local parameter
      const isShadowed = isVariableShadowed(variableName, from, scopes);

      if (!isShadowed && isReactiveVariable(variableName, options)) {
        ranges.push({ from, to, variableName });
      }
    }
  } while (cursor.next());

  return ranges;
}

/**
 * Determines if a variable is reactive (declared in other cells and used in current cell).
 */
function isReactiveVariable(
  variableName: VariableName,
  context: { cellId: CellId; variables: Variables },
): boolean {
  const variable = context.variables[variableName];

  if (!variable) {
    // Variable not tracked by marimo yet - happens when cells haven't been run
    // or when referencing undefined variables
    return false;
  }

  // Variable is reactive if:
  // 1. It's declared by other cells (not the current cell)
  const declaredByOtherCells =
    variable.declaredBy.length > 0 &&
    !variable.declaredBy.includes(context.cellId);

  return declaredByOtherCells;
}

/**
 * Builds a list of scopes (functions, lambdas, comprehensions) with their parameters.
 */
function buildScopes(tree: any, sourceCode: string): Scope[] {
  const scopes: Scope[] = [];
  const cursor = tree.cursor();

  do {
    const { name, from, to } = cursor;

    if (name === "FunctionDefinition") {
      const parameters = extractFunctionParameters(cursor, sourceCode);
      const localDeclarations = new Set<string>();
      scopes.push({
        type: "function",
        start: from,
        end: to,
        parameters,
        localDeclarations,
      });
    } else if (name === "LambdaExpression") {
      const parameters = extractLambdaParameters(cursor, sourceCode);
      const localDeclarations = new Set<string>();
      scopes.push({
        type: "lambda",
        start: from,
        end: to,
        parameters,
        localDeclarations,
      });
    } else if (isComprehensionNode(name)) {
      const parameters = extractComprehensionVariables(cursor, sourceCode);
      const localDeclarations = new Set<string>();
      scopes.push({
        type: "comprehension",
        start: from,
        end: to,
        parameters,
        localDeclarations,
      });
    }
  } while (cursor.next());

  // Second pass: collect local declarations within each scope
  for (const scope of scopes) {
    collectLocalDeclarations(tree, scope, sourceCode);
  }

  return scopes;
}

/**
 * Checks if a variable at a given position is shadowed by a local parameter or declaration.
 */
function isVariableShadowed(
  variableName: string,
  position: number,
  scopes: Scope[],
): boolean {
  // Find all scopes that contain this position
  const containingScopes = scopes.filter(
    (scope) => position >= scope.start && position <= scope.end,
  );

  // Check if any containing scope has a parameter or local declaration with this name
  return containingScopes.some(
    (scope) =>
      scope.parameters.has(variableName) ||
      scope.localDeclarations.has(variableName),
  );
}

/**
 * Extracts parameter names from a function definition.
 */
function extractFunctionParameters(
  cursor: any,
  sourceCode: string,
): Set<string> {
  const parameters = new Set<string>();
  const functionCursor = cursor.node.cursor();

  do {
    if (functionCursor.name === "ParamList") {
      // Create a cursor that only traverses within the ParamList node
      const paramListNode = functionCursor.node;
      const paramCursor = paramListNode.cursor();

      // Only traverse within the ParamList boundaries
      const paramListEnd = functionCursor.to;

      do {
        if (
          paramCursor.name === "VariableName" &&
          paramCursor.to <= paramListEnd
        ) {
          const { from, to } = paramCursor;
          const paramName = sourceCode.slice(from, to);
          parameters.add(paramName);
        }
      } while (paramCursor.next() && paramCursor.from < paramListEnd);

      break; // Found ParamList, we're done
    }
  } while (functionCursor.next());
  return parameters;
}

/**
 * Extracts parameter names from a lambda expression.
 */
function extractLambdaParameters(cursor: any, sourceCode: string): Set<string> {
  const parameters = new Set<string>();
  const lambdaCursor = cursor.node.cursor();

  do {
    if (lambdaCursor.name === "ParamList") {
      // Create a cursor that only traverses within the ParamList node
      const paramListNode = lambdaCursor.node;
      const paramCursor = paramListNode.cursor();

      // Only traverse within the ParamList boundaries
      const paramListEnd = lambdaCursor.to;

      do {
        if (
          paramCursor.name === "VariableName" &&
          paramCursor.to <= paramListEnd
        ) {
          const { from, to } = paramCursor;
          const paramName = sourceCode.slice(from, to);
          parameters.add(paramName);
        }
      } while (paramCursor.next() && paramCursor.from < paramListEnd);

      break; // Found ParamList, we're done
    }
  } while (lambdaCursor.next());

  return parameters;
}

/**
 * Extracts loop variables from comprehension expressions.
 */
function extractComprehensionVariables(
  cursor: any,
  sourceCode: string,
): Set<string> {
  const variables = new Set<string>();
  const compCursor = cursor.node.cursor();

  // Look for pattern: VariableName followed by 'for' keyword
  // This captures the loop variable in expressions like [x for x in items]
  let foundFor = false;

  do {
    if (compCursor.name === "for") {
      foundFor = true;
    } else if (foundFor && compCursor.name === "VariableName") {
      // This is likely the loop variable after 'for'
      const { from, to } = compCursor;
      const varName = sourceCode.slice(from, to);
      variables.add(varName);
      foundFor = false; // Reset for next iteration
    }
  } while (compCursor.next());

  return variables;
}

/**
 * Checks if a node type represents a comprehension expression.
 */
function isComprehensionNode(nodeName: string): boolean {
  return [
    "ArrayComprehensionExpression", // [x for x in items]
    "SetComprehensionExpression", // {x for x in items}
    "DictComprehensionExpression", // {k: v for k, v in items}
  ].includes(nodeName);
}

/**
 * Checks if the syntax tree contains any syntax errors.
 * If there are errors, we shouldn't show reactive variable highlighting.
 */
function hasSyntaxErrors(tree: any): boolean {
  const cursor = tree.cursor();

  do {
    // Lezer uses "⚠" as the error node name for syntax errors
    if (cursor.name === "⚠" || cursor.type.isError) {
      return true;
    }
  } while (cursor.next());

  return false;
}

/**
 * Collects local variable declarations within a specific scope.
 * This includes imports, with statements, exception variables, class/function definitions.
 */
function collectLocalDeclarations(
  tree: any,
  scope: Scope,
  sourceCode: string,
): void {
  const cursor = tree.cursor();

  do {
    const { name, from, to } = cursor;

    // Skip if this node is outside our scope
    if (from < scope.start || to > scope.end) {
      continue;
    }

    // Import statements: import os, from x import y
    if (name === "ImportStatement") {
      collectImportVariables(cursor, scope, sourceCode);
    }

    // With statements: with open('file') as f
    else if (name === "WithStatement") {
      collectWithVariables(cursor, scope, sourceCode);
    }

    // Exception handling: except Exception as e
    else if (name === "TryStatement") {
      collectExceptionVariables(cursor, scope, sourceCode);
    }

    // Function definitions: def my_func()
    else if (name === "FunctionDefinition" && from !== scope.start) {
      // Exclude the scope's own function definition
      collectFunctionName(cursor, scope, sourceCode);
    }

    // Class definitions: class MyClass
    else if (name === "ClassDefinition") {
      collectClassName(cursor, scope, sourceCode);
    }
  } while (cursor.next());
}

/**
 * Extracts variable names from import statements.
 */
function collectImportVariables(
  cursor: any,
  scope: Scope,
  sourceCode: string,
): void {
  const importCursor = cursor.node.cursor();

  do {
    // Look for import aliases and imported names
    if (importCursor.name === "VariableName") {
      const { from, to } = importCursor;
      const varName = sourceCode.slice(from, to);
      scope.localDeclarations.add(varName);
    }
  } while (importCursor.next());
}

/**
 * Extracts variable names from with statements (as variables).
 */
function collectWithVariables(
  cursor: any,
  scope: Scope,
  sourceCode: string,
): void {
  const withCursor = cursor.node.cursor();
  let foundAs = false;

  do {
    if (withCursor.name === "as") {
      foundAs = true;
    } else if (foundAs && withCursor.name === "VariableName") {
      const { from, to } = withCursor;
      const varName = sourceCode.slice(from, to);
      scope.localDeclarations.add(varName);
      foundAs = false;
    }
  } while (withCursor.next());
}

/**
 * Extracts exception variable names from try/except blocks.
 */
function collectExceptionVariables(
  cursor: any,
  scope: Scope,
  sourceCode: string,
): void {
  const tryCursor = cursor.node.cursor();
  let foundAs = false;

  do {
    if (tryCursor.name === "as") {
      foundAs = true;
    } else if (foundAs && tryCursor.name === "VariableName") {
      const { from, to } = tryCursor;
      const varName = sourceCode.slice(from, to);
      scope.localDeclarations.add(varName);
      foundAs = false;
    }
  } while (tryCursor.next());
}

/**
 * Extracts function name from function definition.
 */
function collectFunctionName(
  cursor: any,
  scope: Scope,
  sourceCode: string,
): void {
  const funcCursor = cursor.node.cursor();

  do {
    if (funcCursor.name === "VariableName") {
      // First VariableName after "def" is the function name
      const { from, to } = funcCursor;
      const funcName = sourceCode.slice(from, to);
      scope.localDeclarations.add(funcName);
      break;
    }
  } while (funcCursor.next());
}

/**
 * Extracts class name from class definition.
 */
function collectClassName(cursor: any, scope: Scope, sourceCode: string): void {
  const classCursor = cursor.node.cursor();

  do {
    if (classCursor.name === "VariableName") {
      // First VariableName after "class" is the class name
      const { from, to } = classCursor;
      const className = sourceCode.slice(from, to);
      scope.localDeclarations.add(className);
      break;
    }
  } while (classCursor.next());
}
