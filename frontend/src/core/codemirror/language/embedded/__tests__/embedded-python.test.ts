/* Copyright 2026 Marimo. All rights reserved. */

import type { CompletionContext } from "@codemirror/autocomplete";
import { python } from "@codemirror/lang-python";
import { StreamLanguage } from "@codemirror/language";
import { stexMath } from "@codemirror/legacy-modes/mode/stex";
import { EditorState } from "@codemirror/state";
import { classHighlighter, highlightTree } from "@lezer/highlight";
import { parser as markdownParser } from "@lezer/markdown";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import { parsePython, variableCompletionSource } from "../embedded-python";
import { parseLatex } from "../latex";

const IS_ACTIVE = () => true;

describe("parsePython", () => {
  it("should parse Python code blocks", () => {
    const pythonParser = python().language.parser;
    const config = parsePython(pythonParser, IS_ACTIVE);

    expect(config.defineNodes).toMatchObject([
      { name: "Python" },
      { name: "PythonMark" },
    ]);
  });

  const cases = [
    "{math.exp(3)}",
    '${math.exp(3) + len("$}")} $',
    "${math.exp(3)} + {math.sin(3)}$",
    "${math.exp(3)}$",
    "$$ {math.exp(3)} $$",
    String.raw`\({math.exp(3)}\)`,
    String.raw`\[{math.exp(3)}\]`,
    String.raw`\\({math.exp(3)}\\)`,
    String.raw`\\[{math.exp(3)}\\]`,
    String.raw`$\frac{{{math.exp(3)}}}{{2}}$`,
    String.raw`$\{math.exp(3)}$`,
    '${ {"}": math.exp(3)} }$',
    "${math.exp(3):{width}.{precision}f}$",
  ];

  function highlightedProperties(doc: string, prefix: string) {
    const parser = markdownParser.configure([
      parseLatex(StreamLanguage.define(stexMath).parser),
      parsePython(python().language.parser, () => prefix.includes("f")),
    ]);
    const properties: string[] = [];
    highlightTree(parser.parse(doc), classHighlighter, (from, to, classes) => {
      if (classes.split(" ").includes("tok-propertyName")) {
        properties.push(doc.slice(from, to));
      }
    });
    return properties;
  }

  it.each(["f", "rf", "fr"])(
    "highlights interpolation with %s strings",
    (prefix) => {
      for (const doc of cases) {
        expect(highlightedProperties(doc, prefix)).toEqual(
          doc.includes("math.sin") ? ["exp", "sin"] : ["exp"],
        );
      }
    },
  );

  it.each(["", "r"])("does not interpolate %s strings", (prefix) => {
    for (const doc of cases) {
      expect(highlightedProperties(doc, prefix)).toEqual([]);
    }
  });

  it("parses replacement boundaries once for a paragraph with many interpolations", () => {
    const pythonParser = python().language.parser;
    const parse = vi.spyOn(pythonParser, "parse");
    try {
      const doc = "{math.exp(3)} ".repeat(1000);
      const parser = markdownParser.configure([
        parseLatex(StreamLanguage.define(stexMath).parser),
        parsePython(pythonParser, IS_ACTIVE),
      ]);
      const properties: string[] = [];
      highlightTree(
        parser.parse(doc),
        classHighlighter,
        (from, to, classes) => {
          if (classes.split(" ").includes("tok-propertyName")) {
            properties.push(doc.slice(from, to));
          }
        },
      );
      expect(properties).toEqual(Array.from({ length: 1000 }, () => "exp"));
      expect(parse).toHaveBeenCalledTimes(1);
    } finally {
      parse.mockRestore();
    }
  });

  it("preserves raw backslashes between replacements", () => {
    expect(
      highlightedProperties(String.raw`{math.exp(3)} \N{math.sin(3)}`, "rf"),
    ).toEqual(["exp", "sin"]);
  });

  it("finds replacements after triple quotes in markdown text", () => {
    expect(
      highlightedProperties('{math.exp(3)} """ {math.sin(3)}', "f"),
    ).toEqual(["exp", "sin"]);
  });

  it("keeps replacement positions local to each paragraph", () => {
    expect(
      highlightedProperties("${math.exp(3)}$\n\n${math.sin(3)}$", "rf"),
    ).toEqual(["exp", "sin"]);
  });

  it("preserves LaTeX highlighting around Python replacements", () => {
    const doc = String.raw`$\frac{{{math.exp(3)}}}{{2}} + \alpha$`;
    const parser = markdownParser.configure([
      parseLatex(StreamLanguage.define(stexMath).parser),
      parsePython(python().language.parser, IS_ACTIVE),
    ]);
    const highlighted: string[] = [];
    highlightTree(parser.parse(doc), classHighlighter, (from, to) => {
      highlighted.push(doc.slice(from, to));
    });
    expect(highlighted).toEqual(
      expect.arrayContaining(["\\frac", "exp", "\\alpha"]),
    );
  });

  it.each(["${math.exp(3)$", "${math.exp(3)", "${{math.exp(3)}$"])(
    "does not treat incomplete or escaped braces as replacements: %s",
    (doc) => {
      expect(highlightedProperties(doc, "f")).toEqual([]);
    },
  );

  it.each(["f", "rf", "fr"])(
    "keeps doubled braces literal in %s strings",
    (prefix) => {
      for (const doc of [
        "{{math.exp(3)}}",
        "${{math.exp(3)}}$",
        "$ {{{{math.exp(3)}}}} $",
        String.raw`$\{{math.exp(3)}}$`,
        String.raw`$\frac{{1}}{{2}}$`,
      ]) {
        expect(highlightedProperties(doc, prefix)).toEqual([]);
      }
    },
  );
});

describe("variableCompletionSource", () => {
  beforeEach(() => {
    const mockCellId = cellId("cell-1");
    const mockVariables = {
      [variableName("var1")]: {
        name: variableName("var1"),
        dataType: "int",
        declaredBy: [mockCellId],
        usedBy: [mockCellId],
      },
      [variableName("var2")]: {
        name: variableName("var2"),
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
      matchBefore: (_expr: RegExp) => ({ from: 7, to: 8, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (_types: readonly string[]) => null,
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
      matchBefore: (_expr: RegExp) => ({ from: 6, to: 7, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (_types: readonly string[]) => null,
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
      matchBefore: (_expr: RegExp) => ({ from: 12, to: 13, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (_types: readonly string[]) => null,
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
      tokenBefore: (_types: readonly string[]) => null,
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
      matchBefore: (_expr: RegExp) => ({ from: 8, to: 9, text: "v" }),
      state,
      aborted: false,
      tokenBefore: (_types: readonly string[]) => null,
    };

    const result = variableCompletionSource(context as CompletionContext);
    expect(result).toBeNull();
  });
});
