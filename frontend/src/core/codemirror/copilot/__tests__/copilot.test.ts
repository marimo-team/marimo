/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { exportedForTesting } from "../extension";
import { EditorView } from "@codemirror/view";
import type { CopilotGetCompletionsResult } from "../types";

const { getCopilotRequest, getSuggestion } = exportedForTesting;

const OTHER_CODE = "import numpy as np\nimport pandas as pd";

describe("getCopilotRequest", () => {
  it("empty document", () => {
    const view = new EditorView({
      doc: "",
      extensions: [],
    });
    const state = view.state;
    const allCode = state.doc.toString();
    const result = getCopilotRequest(state, allCode);

    expect(result.doc.source).toMatchInlineSnapshot(`""`);
    expect(result.doc.position).toMatchInlineSnapshot(`
      {
        "character": 0,
        "line": 0,
      }
    `);
  });

  it("should create a correct request object - with no code other code, at the beginning", () => {
    const view = new EditorView({
      doc: "x = 1\ny =",
      extensions: [],
    });
    const state = view.state;
    const allCode = state.doc.toString();
    const result = getCopilotRequest(state, allCode);

    expect(result.doc.source).toMatchInlineSnapshot(`
      "x = 1
      y ="
    `);
    expect(result.doc.position).toMatchInlineSnapshot(`
      {
        "character": 0,
        "line": 0,
      }
    `);
  });

  it("should create a correct request object - with no code other code, at the end", () => {
    const view = new EditorView({
      doc: "x = 1\ny =",
      extensions: [],
    });
    // Move cursor to the end of the document
    view.dispatch({
      selection: { anchor: view.state.doc.length },
    });
    const state = view.state;
    const allCode = state.doc.toString();
    const result = getCopilotRequest(state, allCode);

    expect(result.doc.source).toMatchInlineSnapshot(`
      "x = 1
      y ="
    `);
    expect(result.doc.position).toMatchInlineSnapshot(`
      {
        "character": 3,
        "line": 1,
      }
    `);
  });

  it("should create a correct request object - when other code, at the beginning", () => {
    const view = new EditorView({
      doc: "x = 1\ny =",
      extensions: [],
    });
    const state = view.state;
    const allCode = `${OTHER_CODE}\n${state.doc.toString()}`;
    const result = getCopilotRequest(state, allCode);

    expect(result.doc.source).toMatchInlineSnapshot(`
      "import numpy as np
      import pandas as pd
      x = 1
      y ="
    `);
    expect(result.doc.position).toMatchInlineSnapshot(`
      {
        "character": 0,
        "line": 2,
      }
    `);
  });

  it("should create a correct request object - when other code, at the end", () => {
    const view = new EditorView({
      doc: "x = 1\ny =",
      extensions: [],
    });
    // Move cursor to the end of the document
    view.dispatch({
      selection: { anchor: view.state.doc.length },
    });
    const state = view.state;
    const allCode = `${OTHER_CODE}\n${state.doc.toString()}`;
    const result = getCopilotRequest(state, allCode);

    expect(result.doc.source).toMatchInlineSnapshot(`
      "import numpy as np
      import pandas as pd
      x = 1
      y ="
    `);
    expect(result.doc.position).toMatchInlineSnapshot(`
      {
        "character": 3,
        "line": 3,
      }
    `);
  });
});

describe("getSuggestion", () => {
  it("should return an empty string for empty completions", () => {
    const view = new EditorView({
      doc: "mo",
      extensions: [],
    });
    const response = { completions: [] };
    const position = { line: 0, character: 0 };

    const result = getSuggestion(response, position, view.state);

    expect(result).toBe("");
  });

  it("should not trim when startOffset is zero - at the beginning of the line", () => {
    const view = new EditorView({
      doc: "mo",
      extensions: [],
    });
    const response = {
      completions: [
        {
          displayText: "mo.ui.table(",
          position: { line: 0, character: 0 },
        },
      ],
    } as CopilotGetCompletionsResult;

    // We are 2 characters into the line
    const position = { line: 0, character: 0 };
    const result = getSuggestion(response, position, view.state);

    expect(result).toBe("mo.ui.table(");
  });

  it("should not trim when startOffset is zero - in the middle", () => {
    const view = new EditorView({
      doc: "mo",
      extensions: [],
    });
    const response = {
      completions: [
        {
          displayText: ".ui.table(",
          position: { line: 0, character: 2 },
        },
      ],
    } as CopilotGetCompletionsResult;

    // We are 2 characters into the line
    const position = { line: 0, character: 2 };
    const result = getSuggestion(response, position, view.state);

    expect(result).toBe(".ui.table(");
  });

  it("should trim the beginning of displayText when startOffset is negative", () => {
    const view = new EditorView({
      doc: "mo",
      extensions: [],
    });
    const response = {
      completions: [
        {
          displayText: "mo.ui.table(",
          position: { line: 0, character: 0 },
        },
      ],
    } as CopilotGetCompletionsResult;

    // We are 2 characters into the line
    const position = { line: 0, character: 2 };
    const result = getSuggestion(response, position, view.state);

    expect(result).toBe(".ui.table(");
  });

  it("should trim end of displayText when it matches the next characters - on the same line", () => {
    const view = new EditorView({
      doc: "print('hello') # comment",
      // Cursor ------- ^
      extensions: [],
    });
    // Set the cursor to just after the print('hello
    view.dispatch({
      selection: { anchor: 12 },
    });
    const response = {
      completions: [
        {
          displayText: " world')",
          position: { line: 0, character: 12 },
        },
      ],
    } as CopilotGetCompletionsResult;

    // We are 2 characters into the line
    const position = { line: 0, character: 12 };
    const result = getSuggestion(response, position, view.state);

    // If should just be ` world` since we already have a trailing `')`
    expect(result).toBe(" world");
  });

  it("should trim end of displayText when it matches the next characters - on the next line", () => {
    const view = new EditorView({
      doc: `mo.md("""\nhello\n""")`,
      // Cursor ----------- ^
      extensions: [],
    });

    // Set the cursor to just after the `hello`
    view.dispatch({
      selection: { anchor: 15 },
    });
    const textUpToCursor = view.state.doc.sliceString(0, 15);
    expect(textUpToCursor).toBe(`mo.md("""\nhello`);

    const response = {
      completions: [
        {
          displayText: `hello world\n""")`,
          position: { line: 1, character: 0 },
        },
      ],
    } as CopilotGetCompletionsResult;

    // We are 5 characters into the line (past the hello)
    const position = { line: 1, character: 5 };
    const result = getSuggestion(response, position, view.state);

    // If should just be `world` since we already have a trailing `""")`
    expect(result).toBe(" world");
  });
});
