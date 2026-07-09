/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMockObservable } from "@/core/state/__mocks__/mocks";
import type { Observable } from "@/core/state/observable";
import {
  type ActiveLineInfo,
  activeLineTimer,
} from "../line-timing-decorations";

type MockObservable = Observable<ActiveLineInfo | null> & {
  set: (value: ActiveLineInfo | null) => void;
};

function createEditor(
  content: string,
  infoObservable: Observable<ActiveLineInfo | null>,
) {
  const state = EditorState.create({
    doc: content,
    extensions: [python(), activeLineTimer(infoObservable)],
  });

  return new EditorView({
    state,
    parent: document.body,
  });
}

const CODE = `a = 1
b = 2
c = 3`;

describe("line-timing-decorations", () => {
  let view: EditorView | null = null;
  let observable: MockObservable;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(10_000);
    observable = createMockObservable<ActiveLineInfo | null>(null);
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    document.body.innerHTML = "";
    vi.useRealTimers();
  });

  it("highlights the active line and no other", () => {
    view = createEditor(CODE, observable);

    expect(view.dom.querySelector(".cm-timing-current-line")).toBeNull();

    observable.set({ line: 2, startedAtMs: Date.now() });

    const highlighted = view.dom.querySelectorAll(".cm-timing-current-line");
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0].textContent).toContain("b = 2");
  });

  it("keeps the timer empty before the threshold and formats after", () => {
    view = createEditor(CODE, observable);
    observable.set({ line: 1, startedAtMs: Date.now() });

    const timer = view.dom.querySelector(".cm-line-timer");
    expect(timer).not.toBeNull();
    expect(timer?.textContent).toBe("");

    // Still below the 500ms threshold.
    vi.advanceTimersByTime(250);
    expect(timer?.textContent).toBe("");

    // Past the threshold: shows the elapsed time and keeps ticking.
    vi.advanceTimersByTime(500);
    expect(timer?.textContent).toBe("750ms");

    vi.advanceTimersByTime(1000);
    expect(timer?.textContent).toBe("1.75s");
  });

  it("reuses the widget DOM node when startedAtMs is unchanged", () => {
    view = createEditor(CODE, observable);
    observable.set({ line: 1, startedAtMs: Date.now() });

    const before = view.dom.querySelector(".cm-line-timer");
    expect(before).not.toBeNull();

    // A fresh info object for the same line and start time (e.g. a duplicate
    // notification) must not recreate the widget.
    observable.set({ line: 1, startedAtMs: 10_000 });

    expect(view.dom.querySelector(".cm-line-timer")).toBe(before);
  });

  it("clears the timer interval when the widget is destroyed", () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    view = createEditor(CODE, observable);
    observable.set({ line: 1, startedAtMs: Date.now() });

    expect(view.dom.querySelector(".cm-line-timer")).not.toBeNull();
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    const intervalId = setIntervalSpy.mock.results[0].value;

    observable.set(null);

    expect(view.dom.querySelector(".cm-line-timer")).toBeNull();
    expect(clearIntervalSpy).toHaveBeenCalledWith(intervalId);
  });

  it("renders nothing for an out-of-range line", () => {
    view = createEditor(CODE, observable);

    observable.set({ line: 100, startedAtMs: Date.now() });

    expect(view.dom.querySelector(".cm-timing-current-line")).toBeNull();
    expect(view.dom.querySelector(".cm-line-timer")).toBeNull();
  });
});
