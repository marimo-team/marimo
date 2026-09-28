/* Copyright 2026 Marimo. All rights reserved. */

import type { SyntaxNode } from "@lezer/common";
import { parser as pythonParser } from "@lezer/python";
import type { SqlOutputType } from "@/core/config/config-schema";

/**
 * Whether the current environment is Pyodide/WASM
 */
export function isWasm(): boolean {
  // Document is sometimes undefined in CI so we check to reduce flakiness
  return (
    typeof document !== "undefined" &&
    document.querySelector("marimo-wasm") !== null
  );
}

const DUCKDB_USAGE_PATTERN =
  /(^|\n)\s*(?:import\s+[^\n#]*\bduckdb\b|from\s+duckdb\b|[^\n#]*\bduckdb\s*\.)/;
const POLARS_IMPORT_PATTERN =
  /(^|\n)\s*(?:import\s+[^\n#]*\bpolars\b|from\s+polars\b)/;
const MARIMO_SQL_CALLS = new Set(["mo.sql", "marimo.sql"]);
const MARIMO_APP_CALLS = new Set(["mo.App", "marimo.App"]);

export interface SQLPackageNeeds {
  polars: boolean;
  duckdb: boolean;
  pandasForPolars: boolean;
}

interface SQLPackageOptions {
  foundPackages?: ReadonlySet<string>;
  sqlOutput?: SqlOutputType;
}

interface SQLCodeAnalysis {
  appSqlOutput?: SqlOutputType;
  hasOtherSql: boolean;
  hasPolarsSql: boolean;
}

function isQualifiedCall(
  call: SyntaxNode,
  code: string,
  names: ReadonlySet<string>,
): boolean {
  const callee = call.firstChild;
  if (callee?.name !== "MemberExpression") {
    return false;
  }
  const calleeSource = code.slice(callee.from, callee.to).replaceAll(/\s/g, "");
  return names.has(calleeSource);
}

function getKeywordArgument(
  call: SyntaxNode,
  code: string,
  name: string,
): SyntaxNode | null {
  const args = call.getChild("ArgList");
  for (let child = args?.firstChild; child; child = child.nextSibling) {
    if (
      child.name !== "VariableName" ||
      code.slice(child.from, child.to) !== name
    ) {
      continue;
    }
    const assign = child.nextSibling;
    if (
      assign?.name !== "AssignOp" ||
      code.slice(assign.from, assign.to).trim() !== "="
    ) {
      continue;
    }
    let value = assign.nextSibling;
    while (value?.name === "Comment") {
      value = value.nextSibling;
    }
    return value ?? null;
  }
  return null;
}

function getStaticString(node: SyntaxNode | null, code: string): string | null {
  if (!node) {
    return null;
  }
  if (node.name === "String") {
    const literal = code.slice(node.from, node.to);
    const match = /^(?:r|u)?(?<quote>"""|'''|"|')/i.exec(literal);
    const quote = match?.groups?.quote;
    if (!match || !quote || !literal.endsWith(quote)) {
      return null;
    }
    return literal.slice(match[0].length, -quote.length);
  }
  if (node.name === "ParenthesizedExpression") {
    for (let child = node.firstChild; child; child = child.nextSibling) {
      const value = getStaticString(child, code);
      if (value !== null) {
        return value;
      }
    }
    return null;
  }
  if (node.name === "ContinuedString") {
    let value = "";
    let foundString = false;
    for (let child = node.firstChild; child; child = child.nextSibling) {
      if (child.name === "Comment") {
        continue;
      }
      const part = getStaticString(child, code);
      if (part === null) {
        return null;
      }
      foundString = true;
      value += part;
    }
    return foundString ? value : null;
  }
  return null;
}

function hasPolarsEngineArgument(call: SyntaxNode, code: string): boolean {
  return (
    getStaticString(getKeywordArgument(call, code, "engine"), code) === "polars"
  );
}

export function getNotebookSQLOutput(
  code: string,
  defaultOutput: SqlOutputType = "auto",
): SqlOutputType {
  return analyzeSQLCode(code).appSqlOutput ?? defaultOutput;
}

function analyzeSQLCode(code: string): SQLCodeAnalysis {
  let appSqlOutput: SqlOutputType | undefined;
  let hasPolarsSql = false;
  let hasOtherSql = false;
  const cursor = pythonParser.parse(code).cursor();
  do {
    if (cursor.name !== "CallExpression") {
      continue;
    }

    if (isQualifiedCall(cursor.node, code, MARIMO_APP_CALLS)) {
      const value = getStaticString(
        getKeywordArgument(cursor.node, code, "sql_output"),
        code,
      );
      if (
        value === "auto" ||
        value === "native" ||
        value === "polars" ||
        value === "lazy-polars" ||
        value === "pandas"
      ) {
        appSqlOutput = value;
      }
    } else if (isQualifiedCall(cursor.node, code, MARIMO_SQL_CALLS)) {
      if (hasPolarsEngineArgument(cursor.node, code)) {
        hasPolarsSql = true;
      } else {
        hasOtherSql = true;
      }
    }
  } while (cursor.next());
  return { appSqlOutput, hasOtherSql, hasPolarsSql };
}

export function getSQLPackageNeeds(
  code: string,
  options: SQLPackageOptions = {},
): SQLPackageNeeds {
  const { appSqlOutput, hasOtherSql, hasPolarsSql } = analyzeSQLCode(code);

  return {
    polars: hasPolarsSql,
    pandasForPolars:
      (hasPolarsSql || POLARS_IMPORT_PATTERN.test(code)) &&
      (appSqlOutput ?? options.sqlOutput ?? "auto") === "pandas",
    duckdb:
      hasOtherSql ||
      DUCKDB_USAGE_PATTERN.test(code) ||
      options.foundPackages?.has("duckdb") === true,
  };
}

export function prependSQLPackageImports(
  code: string,
  options: SQLPackageOptions = {},
): string {
  const needs = getSQLPackageNeeds(code, options);
  const packages = new Set<string>();

  // PyArrow must be loaded before Polars to avoid a stale optional-dependency
  // cache. Preserve the existing DuckDB + Polars heuristic as well.
  if (
    needs.pandasForPolars ||
    (needs.duckdb && (needs.polars || code.includes("polars")))
  ) {
    packages.add("pyarrow");
  }
  if (needs.duckdb) {
    packages.add("sqlglot");
    packages.add("duckdb");
    packages.add("pandas");
  }
  if (needs.pandasForPolars) {
    packages.add("pandas");
  }
  if (needs.polars) {
    packages.add("sqlglot");
    packages.add("polars");
  }

  if (packages.size === 0) {
    return code;
  }
  const imports = [...packages].map((pkg) => `import ${pkg}`).join("\n");
  return `${imports}\n${code}`;
}

export function shouldLoadDuckDBPackages(
  code: string,
  foundPackages?: ReadonlySet<string>,
): boolean {
  return getSQLPackageNeeds(code, { foundPackages }).duckdb;
}
