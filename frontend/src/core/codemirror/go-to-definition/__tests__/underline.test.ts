/* Copyright 2026 Marimo. All rights reserved. */
import { python } from "@codemirror/lang-python";
import { EditorView } from "@codemirror/view";
import { expect, it, vi } from "vitest";
import { createUnderlinePlugin, underlineField } from "../underline";

it("shares modifier listeners and clears underlines on blur", () => {
  const add = vi.spyOn(window, "addEventListener");
  const remove = vi.spyOn(window, "removeEventListener");
  const views = Array.from(
    { length: 20 },
    () =>
      new EditorView({
        doc: "value",
        extensions: [python(), underlineField, createUnderlinePlugin(vi.fn())],
        parent: document.body,
      }),
  );
  const events = new Set(["keydown", "keyup", "blur", "mouseleave"]);
  expect(add.mock.calls.filter(([name]) => events.has(name))).toHaveLength(4);
  const view = views[0];
  vi.spyOn(view, "posAtCoords").mockReturnValue(2);
  view.dom.dispatchEvent(new MouseEvent("mousemove", { ctrlKey: true }));
  expect(view.state.field(underlineField).size).toBe(1);
  window.dispatchEvent(new Event("blur"));
  expect(view.state.field(underlineField).size).toBe(0);
  for (const view of views) {
    view.destroy();
  }
  expect(remove.mock.calls.filter(([name]) => events.has(name))).toHaveLength(
    4,
  );
  vi.restoreAllMocks();
});

it("keeps navigation active until both modifiers are released", () => {
  const navigate = vi.fn();
  const view = new EditorView({
    doc: "value",
    extensions: [python(), underlineField, createUnderlinePlugin(navigate)],
  });
  vi.spyOn(view, "posAtCoords").mockReturnValue(2);
  view.dom.dispatchEvent(
    new MouseEvent("mousemove", { ctrlKey: true, metaKey: true }),
  );
  window.dispatchEvent(
    new KeyboardEvent("keyup", { key: "Meta", ctrlKey: true }),
  );
  expect(view.state.field(underlineField).size).toBe(1);
  view.dom.dispatchEvent(new MouseEvent("click", { ctrlKey: true }));
  expect(navigate).toHaveBeenCalledWith(view);
  window.dispatchEvent(new KeyboardEvent("keyup", { key: "Control" }));
  expect(view.state.field(underlineField).size).toBe(0);
  navigate.mockClear();
  view.dom.dispatchEvent(new MouseEvent("click"));
  expect(navigate).not.toHaveBeenCalled();
  view.destroy();
});
