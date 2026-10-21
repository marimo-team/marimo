/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { composeStories } from "@storybook/react-vite";
import { act, render } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import * as stories from "../editor.stories";

vi.mock("@/core/codemirror/cm", () => ({
  basicBundle: () => [],
}));

const { Primary } = composeStories(stories);

it("preserves editor changes when the story rerenders with the same theme", () => {
  const { container, rerender } = render(<Primary />);
  const editor = container.querySelector<HTMLElement>(".cm-editor");
  expect(editor).not.toBeNull();
  const view = editor && EditorView.findFromDOM(editor);
  expect(view).toBeDefined();
  if (!view) {
    throw new Error("Editor view was not mounted");
  }

  act(() => {
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: "user edit" },
    });
  });
  rerender(<Primary />);

  expect(container.querySelector(".cm-editor")).toBe(editor);
  expect(view.state.doc.toString()).toBe("user edit");
});
