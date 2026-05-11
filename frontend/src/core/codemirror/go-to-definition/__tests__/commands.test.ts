/* Copyright 2026 Marimo. All rights reserved. */

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

  test("selects the nearest in-scope local definition", async () => {
    const code = `\
a = 10

def my_func():
    a = 20
    print(a)`;
    view = createEditor(code);
    const result = goToVariableDefinition(view, "a", code.lastIndexOf("a"));

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      a = 10

      def my_func():
          a = 20
          ^
          print(a)
      "
    `);
  });

  test("selects the nearest in-scope parameter definition", async () => {
    const code = `\
a = 10

def my_func(a):
    print(a)`;
    view = createEditor(code);
    const result = goToVariableDefinition(view, "a", code.lastIndexOf("a"));

    expect(result).toBe(true);
    await tick();
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      a = 10

      def my_func(a):
                  ^
          print(a)
      "
    `);
  });

  test("selects the comprehension target inside a set comprehension", async () => {
    const code = `\
x = 100
s = {x for x in range(10)}`;
    view = createEditor(code);
    // Go-to-definition on the `x` before `for` (the expression part of the
    // comprehension).
    const usagePosition = code.indexOf("{x") + 1;
    const result = goToVariableDefinition(view, "x", usagePosition);

    expect(result).toBe(true);
    await tick();
    // Should jump to the comprehension target `x` (after `for`), not the
    // outer `x = 100`. The Lezer Python grammar emits
    // `SetComprehensionExpression`, but the code looks for `SetComprehension`,
    // so the comprehension never creates a scope and the for-target is not
    // collected — `findScopedDefinitionPosition` returns null and the
    // fallback `findFirstMatchingVariable` lands on `x = 100`.
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      x = 100
      s = {x for x in range(10)}
                 ^
      "
    `);
  });

  test("selects the comprehension target inside a dict comprehension", async () => {
    const code = `\
x = 100
d = {x: x for x in range(10)}`;
    view = createEditor(code);
    const usagePosition = code.indexOf("{x") + 1;
    const result = goToVariableDefinition(view, "x", usagePosition);

    expect(result).toBe(true);
    await tick();
    // Positive control: `DictionaryComprehensionExpression` matches the grammar
    // and is in SCOPE_CREATING_NODES, so this should jump to the comprehension
    // target `x` (after `for`).
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      x = 100
      d = {x: x for x in range(10)}
                    ^
      "
    `);
  });

  test("skips enclosing class scope when resolving from inside a method", async () => {
    const code = `\
x = 100
class Foo:
    x = 10
    def method(self):
        return x`;
    view = createEditor(code);
    // Go-to-definition on the `x` inside `return x`.
    const usagePosition = code.lastIndexOf("x");
    const result = goToVariableDefinition(view, "x", usagePosition);

    expect(result).toBe(true);
    await tick();
    // Should jump to `x = 100` at module scope. In Python, methods do NOT see
    // their enclosing class body's names — class scopes are skipped in LEGB
    // lookup once a function boundary has been crossed. `getScopeChain` walks
    // straight up and pushes the `ClassDefinition` onto the chain, so the
    // method's lookup finds the class-body `x = 10` instead.
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      x = 100
      ^
      class Foo:
          x = 10
          def method(self):
              return x
      "
    `);
  });

  test("resolves a global forward-reference from inside a function", async () => {
    const code = `\
def foo():
    return a

a = 10`;
    view = createEditor(code);
    // Go-to-definition on the `a` inside `return a`.
    const usagePosition = code.indexOf("return a") + "return ".length;
    const result = goToVariableDefinition(view, "a", usagePosition);

    expect(result).toBe(true);
    await tick();
    // Should jump to `a = 10` at the bottom. Python allows forward references
    // from within nested functions to module-level names. POSITION_SENSITIVE_SCOPES
    // includes `"global"`, so the global declaration is filtered out (its `from`
    // is after the usage), the lookup returns null, and the fallback
    // `findFirstMatchingVariable` lands on the `a` inside `return a` — i.e.
    // go-to-definition jumps to itself.
    expect(renderEditorView(view)).toMatchInlineSnapshot(`
      "
      def foo():
          return a

      a = 10
      ^
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
