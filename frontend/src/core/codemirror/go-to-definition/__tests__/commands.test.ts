/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, test } from "vitest";
import { goToVariableDefinition } from "../commands";

async function tick(): Promise<void> {
  await new Promise((resolve) => requestAnimationFrame(resolve));
}

function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [python()],
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

describe("goToVariableDefinition", () => {
  test("selects the variable when it exists", async () => {
    view = createEditor(`\
#comment
myVar = 10
print(myVar)`);
    const result = goToVariableDefinition(view, "myVar");

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      #comment
      myVar = 10
      ^
      print(myVar)
      "
    `);
  });

  test("selects a function declaration", async () => {
    view = createEditor(`\
#comment
def my_func():
    pass

print(my_func)`);
    const result = goToVariableDefinition(view, "my_func");

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      #comment
      def my_func():
          ^
          pass

      print(my_func)
      "
    `);
  });

  test("selects outer-scope variable definition", async () => {
    view = createEditor(`\
x = 10

def my_func(x):
    print(x)

print(x)`);
    const result = goToVariableDefinition(view, "x");

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      x = 10
      ^

      def my_func(x):
          print(x)

      print(x)
      "
    `);
  });

  test("selects outer-scope function declaration", async () => {
    view = createEditor(`\
def x():
    print("hi")

def my_func(x):
    print(x)

print(x)`);
    const result = goToVariableDefinition(view, "x");

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      def x():
          ^
          print("hi")

      def my_func(x):
          print(x)

      print(x)
      "
    `);
  });

  test("does not select the variable when it does not exist", async () => {
    view = createEditor(`\
#comment
myVar = 10
print(myVar)`);
    const result = goToVariableDefinition(view, "nonExistentVar");

    expect(result).toBe(false);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      #comment
      ^
      myVar = 10
      print(myVar)
      "
    `);
  });

  test("does not select the variable when it exists in a comment or string", async () => {
    view = createEditor(`\
#comment
# myVar
print('myVar')`);
    const result = goToVariableDefinition(view, "myVar");
    expect(result).toBe(false);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      #comment
      ^
      # myVar
      print('myVar')
      "
    `);
  });
});

/**
 * Returns a string of the editor's document with the current selection
 * highlighted using carets (`^`). Used for snapshot testing.
 *
 * A single caret marks a cursor; multiple carets mark a selection range.
 *
 * @param view - The CodeMirror EditorView instance.
 * @returns A string with selection markers, suitable for snapshots.
 */
function renderEditorView(view: EditorView) {
  const { from, to } = view.state.selection.main;
  const lines = view.state.doc.toString().split("\n");
  let pos = 0;
  return [
    "",
    ...lines.map((line) => {
      const start = pos;
      const end = pos + line.length;
      pos = end + 1;

      if (from >= start && from <= end) {
        const col = {
          start: from - start,
          end: Math.min(to - start, line.length),
        };
        const marker =
          from === to
            ? "^".padStart(col.start + 1)
            : "^".repeat(col.end - col.start).padStart(col.end);
        return `${line}\n${marker}`;
      }

      return line;
    }),
    "",
  ].join("\n");
}
