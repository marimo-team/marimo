/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as cellsModule from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { useFocusFirstEditor } from "../useFocusFirstEditor";

describe("useFocusFirstEditor", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
    // Mock document.hasFocus() to return true so focus logic runs
    vi.spyOn(document, "hasFocus").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should focus the first non-hidden cell after delay", () => {
    const mockEditor = { focus: vi.fn() };
    const getNotebookSpy = vi
      .spyOn(cellsModule, "getNotebook")
      .mockReturnValue({
        cellIds: ["cell-1", "cell-2"],
        cellData: {
          "cell-1": { config: { hide_code: false } },
          "cell-2": { config: { hide_code: false } },
        },
        cellHandles: {
          "cell-1": { current: { editorView: mockEditor } },
          "cell-2": { current: { editorView: mockEditor } },
        },
      } as unknown as cellsModule.NotebookState);

    renderHook(() => useFocusFirstEditor());

    // Advance timers by the delay (100ms)
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(getNotebookSpy).toHaveBeenCalled();
    expect(mockEditor.focus).toHaveBeenCalled();
  });

  it.each([false, true])(
    "preserves form input focus acquired during startup (shadow DOM: %s)",
    (useShadowRoot) => {
      const host = document.createElement("div");
      const input = document.createElement("input");
      const root = useShadowRoot ? host.attachShadow({ mode: "open" }) : host;
      root.append(input);
      document.body.append(host);
      const editor = new EditorView({ parent: document.body });
      const cellId = CellId.create();
      vi.spyOn(cellsModule, "getNotebook").mockReturnValue({
        ...cellsModule.getNotebook(),
        cellIds: [cellId],
        cellHandles: {
          [cellId]: {
            current: { editorView: editor },
          },
        },
      });

      try {
        renderHook(() => useFocusFirstEditor());
        input.focus();

        act(() => {
          vi.advanceTimersByTime(100);
        });

        expect(
          useShadowRoot
            ? host.shadowRoot?.activeElement
            : document.activeElement,
        ).toBe(input);
      } finally {
        editor.destroy();
        host.remove();
      }
    },
  );

  it("should skip hidden cells when focusing", () => {
    const mockEditor = { focus: vi.fn() };
    const getNotebookSpy = vi
      .spyOn(cellsModule, "getNotebook")
      .mockReturnValue({
        cellIds: ["cell-1", "cell-2"],
        cellData: {
          "cell-1": { config: { hide_code: true } }, // hidden
          "cell-2": { config: { hide_code: false } }, // visible
        },
        cellHandles: {
          "cell-1": { current: { editorView: mockEditor } },
          "cell-2": { current: { editorView: mockEditor } },
        },
      } as unknown as cellsModule.NotebookState);

    renderHook(() => useFocusFirstEditor());

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(getNotebookSpy).toHaveBeenCalled();
    expect(mockEditor.focus).toHaveBeenCalled();
  });

  it("should focus cell from URL if scrollTo parameter exists", () => {
    // Mock location.hash
    const originalHash = window.location.hash;
    Object.defineProperty(window, "location", {
      value: { hash: "#scrollTo=testCell" },
      writable: true,
    });

    // Mock document.querySelector
    const mockElement = document.createElement("div");
    mockElement.scrollIntoView = vi.fn();
    mockElement.focus = vi.fn();
    mockElement.dataset.cellId = "cell-123";

    const querySelectorSpy = vi
      .spyOn(document, "querySelector")
      .mockReturnValue(mockElement as unknown as HTMLElement);

    // The target cell may be offscreen, so its editor is built on demand.
    const mockEditor = { focus: vi.fn() };
    const ensureSpy = vi
      .spyOn(cellsModule, "ensureCellEditorView")
      .mockReturnValue(mockEditor as unknown as EditorView);

    renderHook(() => useFocusFirstEditor());

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(querySelectorSpy).toHaveBeenCalledWith(
      '[data-cell-name="testCell"]',
    );
    // oxlint-disable-next-line typescript/unbound-method
    expect(mockElement.scrollIntoView).toHaveBeenCalled();
    // oxlint-disable-next-line typescript/unbound-method
    expect(mockElement.focus).toHaveBeenCalled();
    expect(ensureSpy).toHaveBeenCalledWith("cell-123");
    expect(mockEditor.focus).toHaveBeenCalled();

    // Restore original hash
    Object.defineProperty(window, "location", {
      value: { hash: originalHash },
      writable: true,
    });
  });

  it("should not focus when document does not have focus", () => {
    // Mock document.hasFocus() to return false (e.g., when embedded in iframe)
    vi.spyOn(document, "hasFocus").mockReturnValue(false);

    const mockEditor = { focus: vi.fn() };
    vi.spyOn(cellsModule, "getNotebook").mockReturnValue({
      cellIds: ["cell-1"],
      cellData: {
        "cell-1": { config: { hide_code: false } },
      },
      cellHandles: {
        "cell-1": { current: { editorView: mockEditor } },
      },
    } as unknown as cellsModule.NotebookState);

    renderHook(() => useFocusFirstEditor());

    act(() => {
      vi.advanceTimersByTime(100);
    });

    // Focus should NOT be called when document doesn't have focus
    expect(mockEditor.focus).not.toHaveBeenCalled();
  });
});
