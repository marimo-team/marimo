/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView, type Tooltip } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import {
  asSignatureHint,
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

  it("keeps and re-anchors the tooltip across edits", () => {
    let state = stateWithHint("plt.plot(", 9);
    // Insert before the tooltip position; it should shift to stay anchored.
    state = state.update({ changes: { from: 0, insert: "xy" } }).state;
    expect(state.field(signatureHintField)?.pos).toBe(11);
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
