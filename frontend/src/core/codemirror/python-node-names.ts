/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Named constants for `@lezer/python` grammar node kinds, referenced
 * throughout the codemirror Python analyzers.
 *
 * See https://code.haverbeke.berlin/lezer/python/src/branch/main/src/python.grammar
 */
export const PyNode = {
  // Names
  VariableName: "VariableName",

  // Declarations / scopes
  FunctionDefinition: "FunctionDefinition",
  ClassDefinition: "ClassDefinition",
  LambdaExpression: "LambdaExpression",
  ParamList: "ParamList",
  Decorator: "Decorator",

  // Statements
  AssignStatement: "AssignStatement",
  ForStatement: "ForStatement",
  ImportStatement: "ImportStatement",
  TryStatement: "TryStatement",
  WithStatement: "WithStatement",

  // Expressions
  TupleExpression: "TupleExpression",
  ArrayExpression: "ArrayExpression",
  ParenthesizedExpression: "ParenthesizedExpression",
  CallExpression: "CallExpression",
  ArgList: "ArgList",
  AssignOp: "AssignOp",
  ArrayComprehensionExpression: "ArrayComprehensionExpression",
  SetComprehensionExpression: "SetComprehensionExpression",
  DictionaryComprehensionExpression: "DictionaryComprehensionExpression",
  ComprehensionExpression: "ComprehensionExpression",

  // Never contain live code
  Comment: "Comment",
  String: "String",
  FormatString: "FormatString",
} as const;

export type PyNodeName = (typeof PyNode)[keyof typeof PyNode];

/**
 * Keyword tokens from the same grammar (also named nodes, just lowercase
 * and not part of `expression`/`statement`).
 */
export const PyKeyword = {
  For: "for",
  In: "in",
  As: "as",
  Import: "import",
} as const;

export type PyKeywordName = (typeof PyKeyword)[keyof typeof PyKeyword];

/**
 * Node kinds that introduce a new variable scope: function/lambda bodies
 * (and their parameters), comprehensions (their loop variables are scoped
 * to the comprehension), and class bodies.
 */
export const SCOPE_CREATING_NODES: ReadonlySet<string> = new Set([
  PyNode.FunctionDefinition,
  PyNode.LambdaExpression,
  PyNode.ArrayComprehensionExpression,
  PyNode.SetComprehensionExpression,
  PyNode.DictionaryComprehensionExpression,
  PyNode.ComprehensionExpression,
  PyNode.ClassDefinition,
]);

/**
 * Node kinds that never contain live code: comments and string/f-string
 * literals.
 *
 * Note `FormatString` nodes *do* contain real, parsed expressions for
 * their `{...}` interpolations (as child `FormatReplacement` nodes) — this
 * set is only safe to use for point checks (e.g. `resolveInner(pos).name`,
 * which already resolves to the innermost node at that exact position) and
 * NOT for pruning a `tree.iterate()` walk, which would also skip those
 * interpolations' real child nodes.
 */
export const NON_CODE_NODES: ReadonlySet<string> = new Set([
  PyNode.Comment,
  PyNode.String,
  PyNode.FormatString,
]);
