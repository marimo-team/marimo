/* Copyright 2026 Marimo. All rights reserved. */

import {
  EditorSelection,
  EditorState,
  type TransactionSpec,
} from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  acceptInlineCompletion,
  inlineCompletion,
  rejectInlineCompletion,
} from "@marimo-team/codemirror-ai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Exercise the installed dependency to catch regressions in upstream releases.
describe("inline completion lifecycle", () => {
  let view: EditorView;
  const fetchFn =
    vi.fn<
      (
        state: EditorState,
        signal: AbortSignal,
        view: EditorView,
      ) => Promise<string>
    >();

  function create(
    options: Partial<Parameters<typeof inlineCompletion>[0]> = {},
  ) {
    view = new EditorView({
      parent: document.body,
      state: EditorState.create({
        doc: "pri",
        selection: { anchor: 3 },
        extensions: [
          EditorState.allowMultipleSelections.of(true),
          inlineCompletion({ delay: 150, fetchFn, ...options }),
        ],
      }),
    });
  }

  function type(text: string) {
    view.dispatch({
      ...view.state.replaceSelection(text),
      userEvent: "input.type",
    });
  }

  function suggestion() {
    return view.dom.querySelector(".cm-inline-suggestion")?.textContent ?? null;
  }

  async function show(text = 't("hello")') {
    fetchFn.mockResolvedValue(text);
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBe(text);
  }

  beforeEach(() => {
    vi.useFakeTimers();
    fetchFn.mockReset().mockResolvedValue('t("hello")');
  });

  afterEach(() => {
    view?.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("debounces bursts and fetches only the latest document at 150ms", async () => {
    create();
    type("n");
    await vi.advanceTimersByTimeAsync(149);
    expect(fetchFn).not.toHaveBeenCalled();
    type("t");
    await vi.advanceTimersByTimeAsync(149);
    expect(fetchFn).not.toHaveBeenCalled();
    const state = view.state;
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchFn).toHaveBeenCalledExactlyOnceWith(
      state,
      expect.objectContaining({ aborted: false }),
      view,
    );
  });

  it.each(["t", 't("', 't("hello'])(
    "retains the suffix immediately after matching input %j",
    async (text) => {
      create();
      await show();
      type(text);
      expect(suggestion()).toBe('t("hello")'.slice(text.length));
      await vi.advanceTimersByTimeAsync(1000);
      expect(fetchFn).toHaveBeenCalledTimes(1);
      expect(acceptInlineCompletion(view)).toBe(true);
      expect(view.state.doc.toString()).toBe('print("hello")');
    },
  );

  it("preserves multiline and UTF-16 suggestions", async () => {
    create();
    await show("😀\nnext()");
    type("😀\n");
    expect(suggestion()).toBe("next()");
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("fetches a continuation when the suggestion is fully typed", async () => {
    create();
    await show("t");
    fetchFn.mockResolvedValue("(value)");
    type("t");
    expect(suggestion()).toBeNull();
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBe("(value)");
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it.each<[string, TransactionSpec]>([
    [
      "mismatch",
      { changes: { from: 4, insert: "x" }, selection: { anchor: 5 } },
    ],
    ["deletion", { changes: { from: 3, to: 4 }, selection: { anchor: 3 } }],
    [
      "replacement",
      { changes: { from: 3, to: 4, insert: "t" }, selection: { anchor: 4 } },
    ],
    [
      "edit away from cursor",
      { changes: { from: 0, insert: "t" }, selection: { anchor: 5 } },
    ],
    [
      "multiple edits",
      {
        changes: [
          { from: 0, insert: "x" },
          { from: 4, insert: "t" },
        ],
        selection: { anchor: 6 },
      },
    ],
    [
      "cursor moved after insertion",
      { changes: { from: 4, insert: "t" }, selection: { anchor: 0 } },
    ],
  ])("discards a suggestion after %s", async (_label, transaction) => {
    create();
    await show();
    view.dispatch(transaction);
    expect(suggestion()).toBeNull();
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("does not reuse suggestions or fetch for multiple cursors", async () => {
    create();
    await show();
    view.dispatch({
      selection: EditorSelection.create(
        [EditorSelection.cursor(0), EditorSelection.cursor(4)],
        1,
      ),
    });
    type("t");
    expect(view.state.doc.toString()).toBe("tprint");
    expect(view.state.selection.toJSON()).toEqual(
      EditorSelection.create(
        [EditorSelection.cursor(1), EditorSelection.cursor(6)],
        1,
      ).toJSON(),
    );
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBeNull();
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("does not fetch when an edit leaves a nonempty selection", async () => {
    create();
    view.dispatch({
      changes: { from: 3, insert: "n" },
      selection: { anchor: 0, head: 4 },
    });
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).not.toHaveBeenCalled();
    expect(suggestion()).toBeNull();
  });

  it("cancels a deferred cache hit before it can display at a new cursor", async () => {
    create();
    await show();
    view.dispatch({ changes: { from: 3, to: 4 }, selection: { anchor: 3 } });
    type("n");
    view.dispatch({ selection: { anchor: 0 } });
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(suggestion()).toBeNull();
  });

  it("ignores a late failure from a cancelled request without hiding its replacement", async () => {
    create();
    const error = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const old = Promise.withResolvers<string>();
    fetchFn.mockReturnValueOnce(old.promise).mockResolvedValueOnce("(new)");
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    type("t");
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBe("(new)");
    old.reject(new Error("old connection failed"));
    await vi.advanceTimersByTimeAsync(0);
    expect(suggestion()).toBe("(new)");
    expect(error).not.toHaveBeenCalled();
  });

  it("cancels scheduled work when the cursor moves", async () => {
    create();
    type("n");
    view.dispatch({ selection: { anchor: 0 } });
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("aborts superseded work and ignores an out-of-order response", async () => {
    create();
    const old = Promise.withResolvers<string>();
    const latest = Promise.withResolvers<string>();
    fetchFn
      .mockReturnValueOnce(old.promise)
      .mockReturnValueOnce(latest.promise);
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    const oldSignal = fetchFn.mock.calls[0][1];
    type("t");
    expect(oldSignal.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(150);
    latest.resolve("(new)");
    await vi.advanceTimersByTimeAsync(0);
    old.resolve("stale");
    await vi.advanceTimersByTimeAsync(0);
    expect(suggestion()).toBe("(new)");
  });

  it("ignores a response after moving away and back to the same cursor", async () => {
    create();
    const result = Promise.withResolvers<string>();
    fetchFn.mockReturnValue(result.promise);
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    view.dispatch({ selection: { anchor: 0 } });
    view.dispatch({ selection: { anchor: 4 } });
    result.resolve("stale");
    await vi.advanceTimersByTimeAsync(0);
    expect(suggestion()).toBeNull();
    expect(fetchFn.mock.calls[0][1].aborted).toBe(true);
  });

  it.each([false, true])(
    "cancels on destruction (already fetching: %s)",
    async (started) => {
      create();
      const result = Promise.withResolvers<string>();
      fetchFn.mockReturnValue(result.promise);
      type("n");
      if (started) {
        await vi.advanceTimersByTimeAsync(150);
      }
      view.destroy();
      result.resolve("stale");
      await vi.advanceTimersByTimeAsync(200);
      expect(fetchFn).toHaveBeenCalledTimes(started ? 1 : 0);
      expect(fetchFn.mock.calls[0]?.[1].aborted).toBe(
        started ? true : undefined,
      );
    },
  );

  it("recovers after a failed request", async () => {
    create();
    const error = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    fetchFn.mockRejectedValueOnce(new Error("offline"));
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBeNull();
    expect(error).toHaveBeenCalledTimes(1);
    type("t");
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBe('t("hello")');
  });

  it("does not log an expected abort rejection", async () => {
    create();
    const error = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    fetchFn.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(error).not.toHaveBeenCalled();
    expect(suggestion()).toBeNull();
  });

  it("respects fetch/display gates and Escape rejection", async () => {
    const before = vi.fn(() => false);
    const display = vi.fn(() => false);
    create({
      events: { beforeSuggestionFetch: before, shouldShowSuggestion: display },
    });
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).not.toHaveBeenCalled();
    before.mockReturnValue(true);
    type("t");
    await vi.advanceTimersByTimeAsync(150);
    expect(suggestion()).toBeNull();
    display.mockReturnValue(true);
    type("(");
    await vi.advanceTimersByTimeAsync(150);
    expect(rejectInlineCompletion(view)).toBe(true);
    expect(suggestion()).toBeNull();
    expect(acceptInlineCompletion(view)).toBe(false);
  });

  it("reuses a cached result without dispatching during a view update", async () => {
    create();
    await show();
    view.dispatch({ changes: { from: 3, to: 4 }, selection: { anchor: 3 } });
    type("n");
    expect(() => view.dispatch({})).not.toThrow();
    await vi.advanceTimersByTimeAsync(0);
    expect(suggestion()).toBe('t("hello")');
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("does not reuse the same document's cached suggestion at a different cursor", async () => {
    create();
    await show();
    view.dispatch({ changes: { from: 3, to: 4 }, selection: { anchor: 3 } });
    view.dispatch({
      changes: { from: 3, insert: "n" },
      selection: { anchor: 0 },
    });
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(fetchFn.mock.calls[1][0].selection.main.head).toBe(0);
  });

  it("expires cached results", async () => {
    create({ cacheTimeout: 100 });
    await show();
    await vi.advanceTimersByTimeAsync(101);
    view.dispatch({ changes: { from: 3, to: 4 }, selection: { anchor: 3 } });
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });
  it("bounds the cache instead of retaining every document ever typed", async () => {
    create({ delay: 0, cacheTimeout: 1_000_000 });
    await show();
    for (let i = 0; i < 21; i++) {
      const text = `entry${i}`;
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: text },
        selection: { anchor: text.length },
      });
      await vi.advanceTimersByTimeAsync(0);
    }
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: "prin" },
      selection: { anchor: 4 },
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchFn).toHaveBeenCalledTimes(23);
  });

  it("does not cache empty results", async () => {
    create();
    fetchFn.mockResolvedValueOnce("");
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    view.dispatch({ changes: { from: 3, to: 4 }, selection: { anchor: 3 } });
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(suggestion()).toBe('t("hello")');
  });
});
