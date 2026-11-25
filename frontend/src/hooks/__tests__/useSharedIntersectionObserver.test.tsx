/* Copyright 2026 Marimo. All rights reserved. */
import { act, cleanup, renderHook } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { mockIntersectionObservers } from "@/__mocks__/intersection-observer";
import { createSharedIntersectionObserver } from "@/utils/shared-intersection-observer";
import { useSharedIntersectionObserver } from "../useSharedIntersectionObserver";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("releases disabled subscriptions and resumes with the current callback", () => {
  const observers = mockIntersectionObservers();
  const subscribe = createSharedIntersectionObserver({});
  const target = createRef<HTMLDivElement>();
  target.current = document.createElement("div");
  const first = vi.fn();
  const second = vi.fn();
  const hook = renderHook(
    ({ enabled, onChange }) =>
      useSharedIntersectionObserver(target, subscribe, onChange, enabled),
    { initialProps: { enabled: false, onChange: first } },
  );
  expect(observers).toHaveLength(0);
  hook.rerender({ enabled: true, onChange: first });
  act(() => observers[0].emit(target.current!, true));
  expect(first).toHaveBeenLastCalledWith(true);
  hook.rerender({ enabled: false, onChange: first });
  expect(first).toHaveBeenLastCalledWith(false);
  expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
  hook.rerender({ enabled: true, onChange: second });
  act(() => {
    observers[0].emit(target.current!, true);
    observers[1].emit(target.current!, true);
  });
  expect(first.mock.calls).toEqual([[true], [false]]);
  expect(second.mock.calls).toEqual([[true]]);
  hook.unmount();
  expect(second.mock.calls).toEqual([[true], [false]]);
  expect(observers[1].disconnect).toHaveBeenCalledTimes(1);
});

it("does not resubscribe on unrelated renders", () => {
  const observers = mockIntersectionObservers();
  const subscribe = createSharedIntersectionObserver({});
  const target = createRef<HTMLDivElement>();
  target.current = document.createElement("div");
  const onChange = vi.fn();
  const hook = renderHook(() =>
    useSharedIntersectionObserver(target, subscribe, onChange),
  );
  hook.rerender();
  hook.rerender();
  expect(observers).toHaveLength(1);
  expect(observers[0].observe).toHaveBeenCalledTimes(1);
  expect(onChange).not.toHaveBeenCalled();
  hook.unmount();
  expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
});
