/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView, type Tooltip } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import {
  asSignatureHint,
  closeSignatureHint,
  setSignatureHintEffect,
  signatureHintField,
} from "../signature-hint";

function fakeTooltip(pos: number): Tooltip {
  return {
    pos,
    above: true,
    create: () => ({ dom: document.createElement("div") }),
  };
}

function stateWithHint(doc: string, pos: number): EditorState {
  const state = EditorState.create({
    doc,
    extensions: [signatureHintField],
  });
  return state.update({ effects: setSignatureHintEffect.of(fakeTooltip(pos)) })
    .state;
}

describe("signatureHintField", () => {
  it("starts empty", () => {
    const state = EditorState.create({ extensions: [signatureHintField] });
    expect(state.field(signatureHintField)).toBeNull();
  });

  it("shows a tooltip when the effect is dispatched", () => {
    const state = stateWithHint("plt.plot(", 9);
    expect(state.field(signatureHintField)?.pos).toBe(9);
  });

  it("clears the tooltip when the effect dispatches null", () => {
    let state = stateWithHint("plt.plot(", 9);
    state = state.update({
      effects: setSignatureHintEffect.of(null),
    }).state;
    expect(state.field(signatureHintField)).toBeNull();
  });

  it("dismisses the tooltip on a selection-only change", () => {
    let state = stateWithHint("plt.plot(x)", 9);
    state = state.update({ selection: { anchor: 0 } }).state;
    expect(state.field(signatureHintField)).toBeNull();
  });

  it("keeps and re-anchors the tooltip across edits inside the call", () => {
    let state = stateWithHint("plt.plot(", 9);
    // Insert before the tooltip position while the cursor stays inside the
    // call; the anchor should shift but the hint should remain.
    state = state.update({
      changes: { from: 0, insert: "xy" },
      selection: { anchor: 11 },
    }).state;
    expect(state.field(signatureHintField)?.pos).toBe(11);
  });

  it("dismisses the tooltip when the closing paren is typed", () => {
    let state = stateWithHint("plt.plot(", 9);
    // Type the closing paren; the cursor is now outside the call.
    state = state.update({
      changes: { from: 9, insert: ")" },
      selection: { anchor: 10 },
    }).state;
    expect(state.field(signatureHintField)).toBeNull();
  });

  it("dismisses the tooltip when the anchored call closes inside grouping parens", () => {
    // Regression for the `(plt.plot())` case: the outer grouping paren must not
    // keep the (now-closed) plt.plot hint alive.
    let state = stateWithHint("(plt.plot(", 10);
    // Close plt.plot's call; the outer `(` is still open but we've left the
    // anchored call.
    state = state.update({
      changes: { from: 10, insert: ")" },
      selection: { anchor: 11 },
    }).state;
    expect(state.field(signatureHintField)).toBeNull();
  });

  it("keeps the tooltip while typing a nested call inside the anchored call", () => {
    // Cursor inside the anchored call of `f(g(<cursor>`; opening/typing a nested
    // call stays inside the anchored call, so the hint should remain.
    let state = stateWithHint("f(g(", 4);
    state = state.update({
      changes: { from: 4, insert: "x(" },
      selection: { anchor: 6 },
    }).state;
    expect(state.field(signatureHintField)?.pos).toBe(4);
  });

  it("keeps the tooltip when a nested call closes inside the anchored call", () => {
    const anchor = "f(".length;
    let state = stateWithHint("f(g(x", anchor);
    state = state.update({
      changes: { from: 5, insert: ")" },
      selection: { anchor: 6 },
    }).state;
    expect(state.field(signatureHintField)?.pos).toBe(anchor);
  });

  it("dismisses the tooltip when the closing paren is typed in a large multi-line call", () => {
    const anchor = "f(".length;
    const prefix = `f(\n${"  x,\n".repeat(25)}`;
    let state = EditorState.create({
      doc: prefix,
      selection: { anchor: prefix.length },
      extensions: [signatureHintField],
    });
    state = state.update({
      effects: setSignatureHintEffect.of(fakeTooltip(anchor)),
    }).state;
    const head = prefix.length;
    state = state.update({
      changes: { from: head, insert: ")" },
      selection: { anchor: head + 1 },
    }).state;
    expect(state.field(signatureHintField)).toBeNull();
  });
});

describe("asSignatureHint", () => {
  it("nests the content so descendant styling applies", () => {
    const content = document.createElement("span");
    content.classList.add("mo-cm-tooltip", "docs-documentation");
    const base: Tooltip = {
      pos: 0,
      create: () => ({ dom: content, resize: false }),
    };

    const view = new EditorView({ state: EditorState.create({}) });
    const { dom } = asSignatureHint(base).create(view);

    // Outer wrapper carries the tooltip sizing class...
    expect(dom.classList.contains("mo-cm-tooltip")).toBe(true);
    // ...and the documentation content is a descendant (not the same node),
    // so `.cm-tooltip .docs-documentation` padding/font rules match.
    expect(dom).not.toBe(content);
    expect(dom.querySelector(".docs-documentation")).toBe(content);

    view.destroy();
  });

  it("preserves other tooltip fields", () => {
    const base: Tooltip = {
      pos: 5,
      above: true,
      create: () => ({ dom: document.createElement("span"), resize: false }),
    };
    const wrapped = asSignatureHint(base);
    expect(wrapped.pos).toBe(5);
    expect(wrapped.above).toBe(true);
  });
});

describe("closeSignatureHint", () => {
  it("returns false when no hint is showing", () => {
    const view = new EditorView({
      state: EditorState.create({ extensions: [signatureHintField] }),
    });
    expect(closeSignatureHint(view)).toBe(false);
    expect(view.state.field(signatureHintField)).toBeNull();
    view.destroy();
  });

  it("dismisses the hint and returns true when one is showing", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "plt.plot(",
        extensions: [signatureHintField],
      }),
    });
    view.dispatch({ effects: setSignatureHintEffect.of(fakeTooltip(9)) });
    expect(view.state.field(signatureHintField)?.pos).toBe(9);

    expect(closeSignatureHint(view)).toBe(true);
    expect(view.state.field(signatureHintField)).toBeNull();
    view.destroy();
  });
});
