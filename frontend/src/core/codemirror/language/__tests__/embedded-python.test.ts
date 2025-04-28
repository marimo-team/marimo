/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, beforeEach } from "vitest";
import { parsePython, variableCompletionSource } from "../embedded-python";
import { EditorState } from "@codemirror/state";
import { python } from "@codemirror/lang-python";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { Variables, VariableName } from "@/core/variables/types";
import type { CellId } from "@/core/cells/ids";
import type { CompletionContext } from "@codemirror/autocomplete";
import type { InlineContext } from "@lezer/markdown";

const IS_ACTIVE = () => true;

describe("parsePython", () => {
  it("should parse Python code blocks", () => {
    const pythonParser = python().language.parser;
    const config = parsePython(pythonParser, IS_ACTIVE);

    expect(config.defineNodes).toBeDefined();
    if (config.defineNodes) {
      expect(config.defineNodes).toHaveLength(2);
      // @ts-expect-error - we know that the defineNodes are NodeSpec
      expect(config.defineNodes[0].name).toBe("Python");
      // @ts-expect-error - we know that the defineNodes are NodeSpec
      expect(config.defineNodes[1].name).toBe("PythonMark");
    }
  });

  it("should not parse double curly braces", () => {
    const pythonParser = python().language.parser;
    const config = parsePython(pythonParser, IS_ACTIVE);

    // Create a mock context
    const mockContext = {
      slice: (from: number, to: number) => {
        if (from === 5 && to === 6) {
          return "{";
        }
        return "";
      },
      addDelimiter: () => -1,
    } as unknown as InlineContext;

    // Test with double curly braces
    const result = config.parseInline![0].parse(mockContext, 123, 6); // 123 is OPEN_BRACE
    expect(result).toBe(-1);
  });
});

describe("variableCompletionSource", () => {
  beforeEach(() => {
    const mockCellId = "cell-1" as CellId;
    const mockVariables: Variables = {
      ["var1" as VariableName]: {
        name: "var1" as VariableName,
        dataType: "int",
        declaredBy: [mockCellId],
        usedBy: [mockCellId],
      },
      ["var2" as VariableName]: {
        name: "var2" as VariableName,
        dataType: "str",
        declaredBy: [mockCellId],
        usedBy: [mockCellId],
      },
    };
    store.set(variablesAtom, mockVariables);
  });

  it("should provide completions inside {} block", () => {
    const state = EditorState.create({
      doc: "print({v",
    });

    const context: Partial<CompletionContext> = {
      pos: 8,
      explicit: false,
      matchBefore: (expr: RegExp) => ({ from: 7, to: 8, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeDefined();
    expect(result?.options).toHaveLength(2);
    expect(result?.from).toBe(7);
  });

  it("should not provide completions outside {} block", () => {
    const state = EditorState.create({
      doc: "print(v",
    });

    const context: Partial<CompletionContext> = {
      pos: 7,
      explicit: false,
      matchBefore: (expr: RegExp) => ({ from: 6, to: 7, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeNull();
  });

  it("should not provide completions after closing brace", () => {
    const state = EditorState.create({
      doc: "print({var1}v",
    });

    const context: Partial<CompletionContext> = {
      pos: 13,
      explicit: false,
      matchBefore: (expr: RegExp) => ({ from: 12, to: 13, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeNull();
  });

  it("should not provide completions for non-word characters", () => {
    const state = EditorState.create({
      doc: "print({+",
    });

    const context: Partial<CompletionContext> = {
      pos: 8,
      explicit: false,
      matchBefore: () => null,
      state,
      aborted: false,
      tokenBefore: (types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeNull();
  });

  it("should not provide completions for double curly braces", () => {
    const state = EditorState.create({
      doc: "print({{v",
    });

    const context: Partial<CompletionContext> = {
      pos: 9,
      explicit: false,
      matchBefore: (expr: RegExp) => ({ from: 8, to: 9, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeNull();
  });
});
