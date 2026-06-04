/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { describe, expect, test, vi } from "vitest";
import { getDeclarations, findScopedDefinitionPosition, findFirstMatchingVariable } from "../commands";

// Mock store to avoid Jotai dependencies in pure tests
vi.mock("../../state/jotai", () => ({
  store: {
    get: vi.fn(),
  },
}));

// Mock notebook atom
vi.mock("../../cells/cells", () => ({
  notebookAtom: {},
}));

function createEditorState(content: string) {
  return EditorState.create({
    doc: content,
    extensions: [python()],
  });
}

describe("Go to Definition: Pure Resolution", () => {
  test("shadowing: local parameter shadows global", () => {
    const code = `\
x = 10
def foo(x):
    print(x)`;
    const state = createEditorState(code);
    const usagePos = code.lastIndexOf("x");
    const result = findScopedDefinitionPosition(state, "x", usagePos);
    
    // Should point to the parameter 'x' in 'foo(x)', not the global 'x = 10'
    const paramPos = code.indexOf("(x") + 1;
    expect(result).toBe(paramPos);
  });

  test("basic resolution: x = 10", () => {
    const code = "x = 10";
    const state = createEditorState(code);
    const decls = getDeclarations(state, "x");
    
    expect(decls).toHaveLength(1);
    expect(decls[0].from).toBe(0);
  });

  test("deterministic tie-break: last assignment in cell wins", () => {
    const code = `\
x = 1
x = 2
print(x)`;
    const state = createEditorState(code);
    const usagePos = code.lastIndexOf("x");
    const result = findScopedDefinitionPosition(state, "x", usagePos);
    
    // Should point to 'x = 2', not 'x = 1'
    expect(result).toBe(code.indexOf("x = 2"));
  });

  test("AST fallback: VariableName nodes only", () => {
    const code = `\
# x in comment
s = "x in string"
print(x)`;
    const state = createEditorState(code);
    const result = findFirstMatchingVariable(state, "x");
    
    // Should only match the 'x' in 'print(x)'
    expect(result).toBe(code.lastIndexOf("x"));
  });
});
