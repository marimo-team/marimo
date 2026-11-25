/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createDebouncedEditorUpdate } from "../debounced-editor-update";

describe("debounced editor updates", () => {
  let view: EditorView;
  beforeEach(() => {
    vi.useFakeTimers();
    view = new EditorView({ doc: "initial" });
  });
  afterEach(() => {
    view.destroy();
    vi.useRealTimers();
  });

  it("coalesces invalidations and reads the latest state at dispatch time", async () => {
    const compute = vi.fn(() => ({
      selection: { anchor: view.state.doc.length },
    }));
    const update = createDebouncedEditorUpdate(view, compute);
    const dispatch = vi.spyOn(view, "dispatch");
    for (let i = 0; i < 500; i++) {
      update.schedule();
    }
    vi.advanceTimersByTime(300);
    expect(compute).not.toHaveBeenCalled();
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: "latest" },
    });
    dispatch.mockClear();
    await Promise.resolve();
    expect(compute).toHaveBeenCalledOnce();
    expect(dispatch).toHaveBeenCalledOnce();
    expect(view.state.selection.main.anchor).toBe(6);
    update.destroy();
  });

  it.each([false, true])(
    "cancels work on destroy (already queued: %s)",
    async (queued) => {
      const compute = vi.fn(() => ({}));
      const update = createDebouncedEditorUpdate(view, compute);
      update.schedule();
      if (queued) {
        vi.advanceTimersByTime(300);
      }
      update.destroy();
      update.destroy();
      update.schedule();
      vi.advanceTimersByTime(300);
      await Promise.resolve();
      expect(compute).not.toHaveBeenCalled();
    },
  );

  it("supersedes queued work when invalidated again", async () => {
    const compute = vi.fn(() => undefined);
    const update = createDebouncedEditorUpdate(view, compute);
    const dispatch = vi.spyOn(view, "dispatch");
    update.schedule();
    vi.advanceTimersByTime(300);
    update.schedule();
    await Promise.resolve();
    expect(compute).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    expect(compute).toHaveBeenCalledOnce();
    expect(dispatch).not.toHaveBeenCalled();
    update.destroy();
  });
});
