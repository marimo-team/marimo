/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { act, cleanup, render } from "@testing-library/react";
import { Activity, StrictMode, createRef } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mockIntersectionObservers } from "@/__mocks__/intersection-observer";
import { editorMountScheduler } from "../editor-mount-scheduler";
import { useLazyEditorMount } from "../use-lazy-editor-mount";

const { tasks } = vi.hoisted(() => ({ tasks: [] as (() => void)[] }));
vi.mock("@/utils/schedule-task", () => ({
  scheduleTask: (task: () => void) => tasks.push(task),
}));

function flush() {
  act(() => {
    while (tasks.length) {
      tasks.shift()?.();
    }
  });
}

afterEach(() => {
  cleanup();
  flush();
  vi.unstubAllGlobals();
});

it("uses current code, builds once, and stops observing after mounting in StrictMode", () => {
  const observers = mockIntersectionObservers();
  const editorViewRef = createRef<EditorView>();
  const build = vi.fn((code: string) => {
    editorViewRef.current = new EditorView({ doc: code });
  });
  function Cell({ code }: { code: string }) {
    const { elementRef, mounted } = useLazyEditorMount({
      cellId: "cell",
      editorViewRef,
      build: () => build(code),
      hidden: false,
    });
    return <div ref={elementRef}>{mounted ? "editor" : "static"}</div>;
  }
  const screen = render(
    <StrictMode>
      <Cell code="old" />
    </StrictMode>,
  );
  screen.rerender(
    <StrictMode>
      <Cell code="new" />
    </StrictMode>,
  );
  expect(build).not.toHaveBeenCalled();
  const observer = observers.at(-1)!;
  act(() => observer.emit(screen.container.firstElementChild!, true));
  flush();
  expect(build).toHaveBeenCalledExactlyOnceWith("new");
  expect(screen.container.textContent).toBe("editor");
  expect(observer.disconnect).toHaveBeenCalledTimes(1);
  act(() => editorMountScheduler.promote("cell"));
  expect(build).toHaveBeenCalledTimes(1);
  const destroy = vi.spyOn(editorViewRef.current!, "destroy");
  screen.unmount();
  expect(destroy).toHaveBeenCalledTimes(1);
  expect(editorViewRef.current).toBeNull();
});

it("does not build hidden code; cancels queued work on hide and unmount", () => {
  const observers = mockIntersectionObservers();
  const editorViewRef = createRef<EditorView>();
  const build = vi.fn(() => {
    editorViewRef.current = new EditorView();
  });
  function Cell({ hidden }: { hidden: boolean }) {
    const { elementRef } = useLazyEditorMount({
      cellId: "cell",
      editorViewRef,
      build,
      hidden,
    });
    return <div ref={elementRef} />;
  }
  const screen = render(<Cell hidden={true} />);
  expect(observers).toHaveLength(0);
  flush();
  expect(build).not.toHaveBeenCalled();
  screen.rerender(<Cell hidden={false} />);
  act(() => observers[0].emit(screen.container.firstElementChild!, true));
  screen.rerender(<Cell hidden={true} />);
  flush();
  expect(build).not.toHaveBeenCalled();
  act(() => editorMountScheduler.promote("cell"));
  expect(build).toHaveBeenCalledTimes(1);
  screen.unmount();

  const pending = render(<Cell hidden={false} />);
  act(() => observers.at(-1)?.emit(pending.container.firstElementChild!, true));
  pending.unmount();
  flush();
  act(() => editorMountScheduler.promote("cell"));
  expect(build).toHaveBeenCalledTimes(1);
});

it("destroys and rebuilds with current code across Activity hide/show", () => {
  mockIntersectionObservers();
  const editorViewRef = createRef<EditorView>();
  const build = vi.fn((code: string) => {
    editorViewRef.current = new EditorView({ doc: code });
  });
  function Cell({ code }: { code: string }) {
    const { elementRef } = useLazyEditorMount({
      cellId: "activity",
      editorViewRef,
      build: () => build(code),
      hidden: false,
    });
    return <div ref={elementRef} />;
  }
  const screen = render(
    <Activity mode="visible">
      <Cell code="first" />
    </Activity>,
  );
  act(() => editorMountScheduler.promote("activity"));
  const first = editorViewRef.current!;
  const destroy = vi.spyOn(first, "destroy");
  screen.rerender(
    <Activity mode="hidden">
      <Cell code="second" />
    </Activity>,
  );
  expect(destroy).toHaveBeenCalledTimes(1);
  expect(editorViewRef.current).toBeNull();
  act(() => editorMountScheduler.promote("activity"));
  expect(build).toHaveBeenCalledTimes(1);
  screen.rerender(
    <Activity mode="visible">
      <Cell code="second" />
    </Activity>,
  );
  act(() => editorMountScheduler.promote("activity"));
  expect(build.mock.calls).toEqual([["first"], ["second"]]);
  expect(editorViewRef.current).not.toBe(first);
  expect(editorViewRef.current?.state.doc.toString()).toBe("second");
});

it("mounts only the three visible editors in a 500-cell notebook", () => {
  const observers = mockIntersectionObservers();
  const views: EditorView[] = [];
  const refs = Array.from({ length: 500 }, () => createRef<EditorView>());
  function Cell({ index }: { index: number }) {
    const { elementRef } = useLazyEditorMount({
      cellId: String(index),
      editorViewRef: refs[index],
      hidden: index % 2 === 0,
      build: () => {
        const view = new EditorView();
        refs[index].current = view;
        views.push(view);
      },
    });
    return <div ref={elementRef} data-cell={index} />;
  }
  const screen = render(
    <>
      {refs.map((_, index) => (
        <Cell key={index} index={index} />
      ))}
    </>,
  );
  expect(observers).toHaveLength(1);
  expect(observers[0].observe).toHaveBeenCalledTimes(250);
  expect(views).toHaveLength(0);
  act(() => {
    for (const index of [1, 3, 5]) {
      observers[0].emit(
        screen.container.querySelector(`[data-cell="${index}"]`)!,
        true,
      );
    }
  });
  flush();
  expect(views).toHaveLength(3);
  const destroys = views.map((view) => vi.spyOn(view, "destroy"));
  screen.unmount();
  flush();
  expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
  for (const destroy of destroys) {
    expect(destroy).toHaveBeenCalledTimes(1);
  }
  expect(refs.every((ref) => ref.current === null)).toBe(true);
});
