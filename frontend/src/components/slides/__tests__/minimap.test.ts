/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { DragMoveEvent } from "@dnd-kit/core";
import { MultiColumn } from "@/utils/id-tree";
import { exportedForTesting } from "../minimap";

const { useVisibleCellIds, projectDropTarget, resolveDropTarget } =
  exportedForTesting;

let intersectionCallback: IntersectionObserverCallback;
let mutationCallback: MutationCallback;
let observeSpy: ReturnType<typeof vi.fn>;
let intersectionDisconnectSpy: ReturnType<typeof vi.fn>;
let mutationDisconnectSpy: ReturnType<typeof vi.fn>;
let mutationObserveSpy: ReturnType<typeof vi.fn>;

function createContainer(...cellIds: string[]): HTMLDivElement {
  const container = document.createElement("div");
  for (const id of cellIds) {
    const child = document.createElement("button");
    child.dataset.cellId = id;
    container.appendChild(child);
  }
  return container;
}

function fakeEntry(
  target: Element,
  isIntersecting: boolean,
): IntersectionObserverEntry {
  return { target, isIntersecting } as unknown as IntersectionObserverEntry;
}

describe("useVisibleCellIds", () => {
  beforeEach(() => {
    observeSpy = vi.fn();
    intersectionDisconnectSpy = vi.fn();
    mutationDisconnectSpy = vi.fn();
    mutationObserveSpy = vi.fn();

    global.IntersectionObserver = class MockIntersectionObserver {
      constructor(
        callback: IntersectionObserverCallback,
        _options?: IntersectionObserverInit,
      ) {
        intersectionCallback = callback;
      }
      observe = observeSpy;
      unobserve = vi.fn();
      disconnect = intersectionDisconnectSpy;
      root = null;
      rootMargin = "";
      thresholds = [0];
      takeRecords = vi.fn(() => []);
    } as unknown as typeof IntersectionObserver;

    global.MutationObserver = class MockMutationObserver {
      constructor(callback: MutationCallback) {
        mutationCallback = callback;
      }
      observe = mutationObserveSpy;
      disconnect = mutationDisconnectSpy;
      takeRecords = vi.fn(() => []);
    } as unknown as typeof MutationObserver;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns an empty set initially", () => {
    const container = createContainer("cell-1");
    const ref = { current: container };

    const { result } = renderHook(() => useVisibleCellIds(ref));

    expect(result.current.size).toBe(0);
  });

  it("observes all [data-cell-id] elements on mount", () => {
    const container = createContainer("a", "b", "c");
    const ref = { current: container };

    renderHook(() => useVisibleCellIds(ref));

    expect(observeSpy).toHaveBeenCalledTimes(3);
  });

  it("does not observe when container ref is null", () => {
    const ref = { current: null };

    const { result } = renderHook(() => useVisibleCellIds(ref));

    expect(observeSpy).not.toHaveBeenCalled();
    expect(result.current.size).toBe(0);
  });

  it("adds cell ids when entries become intersecting", () => {
    const container = createContainer("cell-1", "cell-2");
    const ref = { current: container };
    const children = container.querySelectorAll("[data-cell-id]");

    const { result } = renderHook(() => useVisibleCellIds(ref));

    act(() => {
      intersectionCallback(
        [fakeEntry(children[0], true)],
        {} as IntersectionObserver,
      );
    });

    expect(result.current.has("cell-1" as CellId)).toBe(true);
    expect(result.current.has("cell-2" as CellId)).toBe(false);
  });

  it("removes cell ids when entries stop intersecting", () => {
    const container = createContainer("cell-1");
    const ref = { current: container };
    const children = container.querySelectorAll("[data-cell-id]");

    const { result } = renderHook(() => useVisibleCellIds(ref));

    act(() => {
      intersectionCallback(
        [fakeEntry(children[0], true)],
        {} as IntersectionObserver,
      );
    });
    expect(result.current.has("cell-1" as CellId)).toBe(true);

    act(() => {
      intersectionCallback(
        [fakeEntry(children[0], false)],
        {} as IntersectionObserver,
      );
    });
    expect(result.current.has("cell-1" as CellId)).toBe(false);
  });

  it("preserves set identity when nothing changed", () => {
    const container = createContainer("cell-1");
    const ref = { current: container };
    const children = container.querySelectorAll("[data-cell-id]");

    const { result } = renderHook(() => useVisibleCellIds(ref));

    act(() => {
      intersectionCallback(
        [fakeEntry(children[0], true)],
        {} as IntersectionObserver,
      );
    });
    const firstSet = result.current;

    act(() => {
      intersectionCallback(
        [fakeEntry(children[0], true)],
        {} as IntersectionObserver,
      );
    });
    expect(result.current).toBe(firstSet);
  });

  it("handles batch intersection updates", () => {
    const container = createContainer("a", "b", "c");
    const ref = { current: container };
    const children = container.querySelectorAll("[data-cell-id]");

    const { result } = renderHook(() => useVisibleCellIds(ref));

    act(() => {
      intersectionCallback(
        [
          fakeEntry(children[0], true),
          fakeEntry(children[1], true),
          fakeEntry(children[2], false),
        ],
        {} as IntersectionObserver,
      );
    });

    expect(result.current).toEqual(new Set(["a", "b"]));
  });

  it("ignores entries without data-cell-id", () => {
    const container = createContainer("cell-1");
    const orphan = document.createElement("div");
    container.appendChild(orphan);
    const ref = { current: container };

    const { result } = renderHook(() => useVisibleCellIds(ref));

    act(() => {
      intersectionCallback(
        [fakeEntry(orphan, true)],
        {} as IntersectionObserver,
      );
    });

    expect(result.current.size).toBe(0);
  });

  it("re-observes elements when MutationObserver fires", () => {
    const container = createContainer("cell-1");
    const ref = { current: container };

    renderHook(() => useVisibleCellIds(ref));
    expect(observeSpy).toHaveBeenCalledTimes(1);

    const newChild = document.createElement("button");
    newChild.dataset.cellId = "cell-2";
    container.appendChild(newChild);

    act(() => {
      mutationCallback([], {} as MutationObserver);
    });

    // 1 from initial + 2 from re-observe (observe is idempotent on existing)
    expect(observeSpy).toHaveBeenCalledTimes(3);
  });

  it("disconnects both observers on unmount", () => {
    const container = createContainer("cell-1");
    const ref = { current: container };

    const { unmount } = renderHook(() => useVisibleCellIds(ref));

    // 1 disconnect from the initial observeAll() call
    expect(intersectionDisconnectSpy).toHaveBeenCalledTimes(1);
    expect(mutationDisconnectSpy).not.toHaveBeenCalled();

    unmount();

    // +1 disconnect from cleanup
    expect(intersectionDisconnectSpy).toHaveBeenCalledTimes(2);
    expect(mutationDisconnectSpy).toHaveBeenCalledTimes(1);
  });
});

function rect(top: number, height: number) {
  return { top, height, left: 0, right: 0, bottom: 0, width: 0 };
}

type Rect = ReturnType<typeof rect>;

function fakeDragEvent({
  activeId = "a" as string | number,
  overId = "b" as string | number | null,
  translated = rect(0, 40) as Rect | null,
  initial = undefined as Rect | null | undefined,
  overRect = rect(0, 40),
} = {}): DragMoveEvent {
  return {
    active: {
      id: activeId,
      rect: { current: { translated, initial: initial ?? translated } },
    },
    over: overId === null ? null : { id: overId, rect: overRect },
  } as unknown as DragMoveEvent;
}

describe("projectDropTarget", () => {
  it("returns null when over is null", () => {
    expect(projectDropTarget(fakeDragEvent({ overId: null }))).toBeNull();
  });

  it("returns null when active id is not a string", () => {
    expect(projectDropTarget(fakeDragEvent({ activeId: 42 }))).toBeNull();
  });

  it("returns null when over id is not a string", () => {
    expect(projectDropTarget(fakeDragEvent({ overId: 42 }))).toBeNull();
  });

  it("returns null when active and over are the same cell", () => {
    expect(
      projectDropTarget(fakeDragEvent({ activeId: "x", overId: "x" })),
    ).toBeNull();
  });

  it("returns null when no active rect is available", () => {
    expect(
      projectDropTarget(fakeDragEvent({ translated: null, initial: null })),
    ).toBeNull();
  });

  it("falls back to initial rect when translated is null", () => {
    expect(
      projectDropTarget(
        fakeDragEvent({
          translated: null,
          initial: rect(0, 40),
          overRect: rect(100, 40),
        }),
      ),
    ).toEqual({ overId: "b", position: "before" });
  });

  it("prefers translated rect over initial rect", () => {
    expect(
      projectDropTarget(
        fakeDragEvent({
          translated: rect(200, 40),
          initial: rect(0, 40),
          overRect: rect(100, 40),
        }),
      ),
    ).toEqual({ overId: "b", position: "after" });
  });
});

describe("resolveDropTarget", () => {
  const A = "a" as CellId;
  const B = "b" as CellId;
  const C = "c" as CellId;
  const D = "d" as CellId;

  function makeSingleColumnIds(...ids: CellId[]) {
    return MultiColumn.from([ids]);
  }

  it("returns null when activeId matches target overId", () => {
    const cellIds = makeSingleColumnIds(A, B);
    expect(
      resolveDropTarget({
        cellIds,
        activeId: A,
        target: { overId: A, position: "after" },
      }),
    ).toBeNull();
  });

  it("returns null for multi-column layouts", () => {
    const cellIds = MultiColumn.from([[A, B], [C]]);
    expect(
      resolveDropTarget({
        cellIds,
        activeId: A,
        target: { overId: B, position: "after" },
      }),
    ).toBeNull();
  });

  it('resolves "before" to the over index', () => {
    const cellIds = makeSingleColumnIds(A, B, C);
    const result = resolveDropTarget({
      cellIds,
      activeId: A,
      target: { overId: C, position: "before" },
    });
    expect(result).toEqual({
      cellId: A,
      columnId: cellIds.atOrThrow(0).id,
      index: 2,
    });
  });

  it('resolves "after" to one past the over index', () => {
    const cellIds = makeSingleColumnIds(A, B, C);
    const result = resolveDropTarget({
      cellIds,
      activeId: C,
      target: { overId: A, position: "after" },
    });
    expect(result).toEqual({
      cellId: C,
      columnId: cellIds.atOrThrow(0).id,
      index: 1,
    });
  });

  it('resolves "before" on first item to index 0', () => {
    const cellIds = makeSingleColumnIds(A, B, C);
    const result = resolveDropTarget({
      cellIds,
      activeId: C,
      target: { overId: A, position: "before" },
    });
    expect(result).toEqual({
      cellId: C,
      columnId: cellIds.atOrThrow(0).id,
      index: 0,
    });
  });

  it('resolves "after" on last item to one past the end', () => {
    const cellIds = makeSingleColumnIds(A, B, C, D);
    const result = resolveDropTarget({
      cellIds,
      activeId: A,
      target: { overId: D, position: "after" },
    });
    expect(result).toEqual({
      cellId: A,
      columnId: cellIds.atOrThrow(0).id,
      index: 4,
    });
  });
});
