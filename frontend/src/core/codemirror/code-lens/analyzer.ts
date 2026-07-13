/* Copyright 2026 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";
import type { SyntaxNode, Tree } from "@lezer/common";
import { hasSyntaxErrors } from "../reactive-references/analyzer";

export interface CodeLensTarget {
  from: number;
  to: number;
  name: string;
}

const SCOPE_CREATING_NODES = new Set([
  "FunctionDefinition",
  "LambdaExpression",
  "ArrayComprehensionExpression",
  "SetComprehensionExpression",
  "DictionaryComprehensionExpression",
  "ComprehensionExpression",
  "ClassDefinition",
]);

/**
 * Finds the first module-scope assignment site for each name in `names`.
 */
export function findDeclarationSites(options: {
  state: EditorState;
  names: ReadonlySet<string>;
}): CodeLensTarget[] {
  const { state, names } = options;
  if (names.size === 0) {
    return [];
  }
  const tree = syntaxTree(state);
  if (!tree || hasSyntaxErrors(tree)) {
    return [];
  }

  const firstSites = new Map<string, CodeLensTarget>();

  const collectTargetNames = (node: SyntaxNode) => {
    if (node.name === "VariableName") {
      const name = state.doc.sliceString(node.from, node.to);
      if (names.has(name) && !firstSites.has(name)) {
        firstSites.set(name, { from: node.from, to: node.to, name });
      }
      return;
    }
    // Recurse into tuple/list unpacking, e.g. `(a, b) = ...` or `[a, b] = ...`,
    // and parenthesized targets, e.g. `(df) = ...`.
    // Member/subscript targets (`obj.attr = ...`) are not declarations.
    if (
      node.name === "TupleExpression" ||
      node.name === "ArrayExpression" ||
      node.name === "ParenthesizedExpression"
    ) {
      for (let child = node.firstChild; child; child = child.nextSibling) {
        collectTargetNames(child);
      }
    }
  };

  const collectAssignmentTargets = (assign: SyntaxNode) => {
    // Targets are everything before the last AssignOp (handles `a = b = ...`).
    // A bare annotation (`x: int`) has no AssignOp and is skipped.
    let lastAssignOp = -1;
    for (let child = assign.firstChild; child; child = child.nextSibling) {
      if (child.name === "AssignOp") {
        lastAssignOp = child.from;
      }
    }
    if (lastAssignOp === -1) {
      return;
    }
    for (
      let child = assign.firstChild;
      child && child.from < lastAssignOp;
      child = child.nextSibling
    ) {
      collectTargetNames(child);
    }
  };

  const visit = (node: SyntaxNode) => {
    // Only module-scope assignments count as creation sites; top-level
    // `if`/`for`/`try` bodies are still module scope.
    if (SCOPE_CREATING_NODES.has(node.name)) {
      return;
    }
    if (node.name === "AssignStatement") {
      collectAssignmentTargets(node);
      return;
    }
    for (let child = node.firstChild; child; child = child.nextSibling) {
      visit(child);
    }
  };
  visit(tree.topNode);

  return [...firstSites.values()];
}

const CACHE_PATTERN = /\bmo\.(?:persistent_cache|cache)\b/g;
const NON_CODE_NODES = new Set(["Comment", "String", "FormatString"]);

export interface CacheSite {
  from: number;
  to: number;
  /**
   * Variable the cache is bound to: the decorated function name
   * (`@mo.cache def f`), the assignment target (`g = mo.cache(f)`), or the
   * `as` binding (`with mo.persistent_cache("k") as c`).
   */
  boundName: string | null;
  /** First string argument, e.g. the persistent_cache name. */
  cacheName: string | null;
}

function stripStringQuotes(text: string): string {
  const match = text.match(/^[A-Za-z]*("""|'''|"|')([\s\S]*)\1$/);
  return match ? match[2] : text;
}

/**
 * Resolves a `mo.cache` / `mo.persistent_cache` match into a CacheSite:
 * extends `to` past call arguments (`mo.cache(pin_modules=True)`), so an
 * icon placed at `to` lands after the closing paren, and extracts the bound
 * variable name and the cache-name string argument.
 */
function analyzeCacheSite(
  state: EditorState,
  tree: Tree,
  from: number,
  to: number,
): CacheSite {
  const text = (node: SyntaxNode) => state.doc.sliceString(node.from, node.to);
  const node = tree.resolveInner(from, 1);
  let boundName: string | null = null;
  let argList: SyntaxNode | null = null;
  let end = to;

  // `mo.cache(...)` as an expression wraps in a CallExpression that starts
  // at the match
  let call: SyntaxNode | null = null;
  for (
    let ancestor: SyntaxNode | null = node.parent;
    ancestor && ancestor.from === from;
    ancestor = ancestor.parent
  ) {
    if (ancestor.name === "CallExpression") {
      call = ancestor;
      break;
    }
  }

  if (call) {
    end = call.to;
    argList = call.getChild("ArgList");
    const parent = call.parent;
    if (parent?.name === "AssignStatement") {
      // `g = mo.cache(f)` — the direct VariableName child is the target
      const target = parent.getChild("VariableName");
      boundName = target && target.from < call.from ? text(target) : null;
    } else if (parent?.name === "WithStatement") {
      // `with mo.persistent_cache("k") as c:` — `as c` follows the call
      for (let child = parent.firstChild; child; child = child.nextSibling) {
        if (child.from < call.to) {
          continue;
        }
        if (child.name === "as") {
          continue;
        }
        if (child.name === "VariableName") {
          boundName = text(child);
        }
        break;
      }
    }
  } else if (node.parent?.name === "Decorator") {
    // `@mo.cache(...)` decorators are flat: the ArgList is a direct sibling
    const decorator = node.parent;
    const decoratorArgs = decorator.getChild("ArgList");
    if (decoratorArgs?.from === to) {
      argList = decoratorArgs;
      end = decoratorArgs.to;
    }
    // The decorated function's name
    const fn = decorator.parent?.getChild("FunctionDefinition");
    const fnName = fn?.getChild("VariableName");
    boundName = fnName ? text(fnName) : null;
  }

  const stringArg = argList?.getChild("String");
  const cacheName = stringArg ? stripStringQuotes(text(stringArg)) : null;
  return { from, to: end, boundName, cacheName };
}

/**
 * True when the `mo` at `from` is a standalone module reference (the object of
 * `mo.cache`), not an attribute of something else. This filters out chains
 * like `obj.mo.cache(f)` — where `mo` is a `PropertyName` rather than a
 * `VariableName` — and mentions inside comments or strings.
 */
function isStandaloneMoReference(
  state: EditorState,
  tree: Tree,
  from: number,
): boolean {
  const node = tree.resolveInner(from, 1);
  if (NON_CODE_NODES.has(node.name)) {
    return false;
  }
  // In `obj.mo.cache`, `mo` parses as a `PropertyName`; a standalone `mo`
  // (including whitespace-separated `mo . cache`) parses as a `VariableName`.
  return (
    node.name === "VariableName" &&
    state.doc.sliceString(node.from, node.to) === "mo"
  );
}

/**
 * Finds occurrences of `mo.cache` / `mo.persistent_cache` (as a decorator,
 * call, or context manager) with a simple text match, skipping mentions in
 * comments, strings, and attribute chains (`obj.mo.cache`). `to` extends past
 * call arguments when present.
 */
export function findCacheSites(state: EditorState): CacheSite[] {
  const tree = syntaxTree(state);
  return [...state.doc.toString().matchAll(CACHE_PATTERN)]
    .filter((match) => isStandaloneMoReference(state, tree, match.index))
    .map((match) =>
      analyzeCacheSite(state, tree, match.index, match.index + match[0].length),
    );
}
