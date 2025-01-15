/* Copyright 2024 Marimo. All rights reserved. */
import type { Tree } from "@lezer/common";
import { parser } from "@lezer/python";
import { LRUCache } from "lru-cache";
import { Logger } from "@/utils/Logger";

const IGNORE_NODES = new Set(["Comment", "LineComment", "BlockComment", " "]);

// Helper function to get a simplified string representation of the AST
function getASTString(tree: Tree, code: string): string {
  const result: string[] = [];
  const cursor = tree.cursor();

  do {
    if (IGNORE_NODES.has(cursor.name)) {
      continue;
    }

    if (cursor.type.isError) {
      result.push(code.slice(cursor.from, cursor.to) || "ERROR");
      continue;
    }

    switch (cursor.name) {
      case "VariableName":
      case "AssignOp":
      case "Number":
      case "String":
      case "Identifier":
      case "ArithOp":
      case "CompareOp":
      case "BinaryOp":
      case "UnaryOp":
        result.push(`${cursor.name}(${code.slice(cursor.from, cursor.to)})`);
        break;
      default:
        if (cursor.name) {
          result.push(cursor.name);
        }
    }
  } while (cursor.next());

  return result.join(":");
}

// LRU cache for parsed trees
const treeCache = new LRUCache<string, Tree>({
  max: 100,
});

function parseAndCache(code: string): Tree {
  const cached = treeCache.get(code);
  if (cached) {
    return cached;
  }

  const tree = parser.parse(code);
  treeCache.set(code, tree);
  return tree;
}

/**
 * Compares two Python code snippets for logical differences,
 * ignoring whitespace, comments, and formatting differences.
 *
 * This function should return as fast as possible.
 *
 * Optimizations that won't work:
 * - Quick comparison after stripping whitespace, because whitespace can
 * exist in strings.
 * - Quick node count comparison, since they may contain comments or other
 * ignored nodes.
 */
export function areLogicallyDifferent(
  code1: string | undefined | null,
  code2: string | undefined | null,
): boolean {
  if (code1 == null || code2 == null) {
    return code1 !== code2;
  }

  code1 = code1.trim();
  code2 = code2.trim();

  // Quick equality check before parsing
  if (code1 === code2) {
    return false;
  }

  // If either code is empty (after trimming), we consider them different
  if (code1 === "" || code2 === "") {
    return true;
  }

  try {
    const tree1 = parseAndCache(code1);
    const tree2 = parseAndCache(code2);

    const ast1String = getASTString(tree1, code1);
    const ast2String = getASTString(tree2, code2);

    return ast1String !== ast2String;
  } catch {
    Logger.error("Failed to parse code", { code1, code2 });
    return code1 !== code2;
  }
}
