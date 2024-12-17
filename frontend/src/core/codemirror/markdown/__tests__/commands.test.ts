/* Copyright 2024 Marimo. All rights reserved. */
import { EditorState, EditorView, basicSetup } from "@uiw/react-codemirror";
import { describe, afterEach, test, expect } from "vitest";
import {
  insertBlockquote,
  insertBoldMarker,
  insertCodeMarker,
  insertImage,
  insertItalicMarker,
  insertLink,
  insertOL,
  insertTextFile,
  insertUL,
} from "../commands";

function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [basicSetup()],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  return view;
}

let view: EditorView | null = null;

afterEach(() => {
  if (view) {
    view.destroy();
    view = null;
  }
});

describe("insertBlockquote", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("> line 1\n> line 2\n> line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("> line 1\n> line 2\n> line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("> line 1\nline 2\n> line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("> line 1\n> line 2\n> line 3");
  });
});

describe("insertUL", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("- line 1\n- line 2\n- line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("- line 1\n- line 2\n- line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("- line 1\nline 2\n- line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("- line 1\n- line 2\n- line 3");
  });
});

describe("insertOL", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("1. line 1\n1. line 2\n1. line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("1. line 1\n1. line 2\n1. line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("1. line 1\nline 2\n1. line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("1. line 1\n1. line 2\n1. line 3");
  });
});

describe("insertLink", () => {
  test("inserts link at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 12 },
    });

    insertLink(view);

    expect(view.state.doc.toString()).toBe("Hello, [world](http://)!");
  });
});

describe("insertImage", () => {
  test("inserts image at cursor position", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    const png = new Uint8Array([1, 2, 3]);
    await insertImage(
      view,
      new File([png], "hello.png", { type: "image/png" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![](data:image/png;base64,AQID)world!"`,
    );
  });

  test("inserts image at cursor position with selected text", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    const png = new Uint8Array([1, 2, 3]);
    await insertImage(
      view,
      new File([png], "hello.png", { type: "image/png" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![world!](data:image/png;base64,AQID)"`,
    );
  });
});

describe("insertTextFile", () => {
  test("inserts text file at cursor position", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    await insertTextFile(
      view,
      new File(["csvcsvcsv"], "my.csv", { type: "text/csv" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, csvcsvcsvworld!"`,
    );
  });

  test("inserts text file at cursor position with selected text", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    await insertTextFile(
      view,
      new File(["csvcsvcsv"], "my.csv", { type: "text/csv" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, csvcsvcsvworld!"`,
    );
  });
});

describe("insertBoldMarker", () => {
  test("inserts bold marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, **world**!");
  });

  test("inserts bold marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, **world!**");
  });

  test("undo bold marker at cursor position with selected text", () => {
    view = createEditor("Hello, **world!**");
    view.dispatch({
      selection: { anchor: 9, head: 15 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, world!");
  });
});

describe("insertItalicMarker", () => {
  test("inserts italic marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, _world_!");
  });

  test("inserts italic marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, _world!_");
  });

  test("undo italic marker at cursor position with selected text", () => {
    view = createEditor("Hello, _world!_");
    view.dispatch({
      selection: { anchor: 8, head: 14 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, world!");
  });
});

describe("insertCodeMarker", () => {
  test("inserts code marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`"Hello, world!"`);
  });

  test("inserts code marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, \`world!\`"`,
    );
  });

  test("undo code marker at cursor position with selected text", () => {
    view = createEditor("Hello, `world!`");
    view.dispatch({
      selection: { anchor: 8, head: 14 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`"Hello, world!"`);
  });

  test("inserts code marker with multiline selection", () => {
    view = createEditor(
      "Here is the python code:\nprint('Hello, world!')\n(1 + 2) * 3",
    );
    view.dispatch({
      selection: { anchor: 25, head: view.state.doc.length },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`
      "Here is the python code:
      \`\`\`
      print('Hello, world!')
      (1 + 2) * 3
      \`\`\`"
    `);
  });

  test("undo code marker with multiline selection", () => {
    view = createEditor(
      "Here is the python code:\n```\nprint('Hello, world!')\n(1 + 2) * 3\n```",
    );
    view.dispatch({
      selection: { anchor: 29, head: view.state.doc.length - 4 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`
      "Here is the python code:
      print('Hello, world!')
      (1 + 2) * 3"
    `);
  });
});
