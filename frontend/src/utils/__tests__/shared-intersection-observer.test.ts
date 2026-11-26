/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, expect, it, vi } from "vitest";
import { mockIntersectionObservers } from "@/__mocks__/intersection-observer";
import { createSharedIntersectionObserver } from "../shared-intersection-observer";

afterEach(() => vi.unstubAllGlobals());

it("shares one observer across 500 nodes and releases each node exactly once", () => {
  const observers = mockIntersectionObservers();
  const subscribe = createSharedIntersectionObserver({});
  const callbacks = Array.from({ length: 500 }, () => vi.fn());
  const nodes = callbacks.map(() => document.createElement("div"));
  const releases = nodes.map((node, i) => subscribe(node, callbacks[i]));
  expect(observers).toHaveLength(1);
  expect(observers[0].observe).toHaveBeenCalledTimes(500);
  observers[0].emit(nodes[300], true);
  expect(callbacks.filter((callback) => callback.mock.calls.length)).toEqual([
    callbacks[300],
  ]);
  for (const release of releases) {
    release();
    release();
  }
  expect(observers[0].unobserve).toHaveBeenCalledTimes(500);
  expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
  observers[0].emit(nodes[300], false);
  expect(callbacks[300]).toHaveBeenCalledExactlyOnceWith(true);
});

it("keeps duplicate subscriptions independent and ignores callbacks from a disposed observer", () => {
  const observers = mockIntersectionObservers();
  const subscribe = createSharedIntersectionObserver({});
  const node = document.createElement("div");
  const callback = vi.fn();
  const first = subscribe(node, callback);
  const second = subscribe(node, callback);
  first();
  expect(observers[0].unobserve).not.toHaveBeenCalled();
  observers[0].emit(node, true);
  expect(callback).toHaveBeenCalledExactlyOnceWith(true);
  second();
  const third = subscribe(node, callback);
  observers[0].emit(node, false);
  expect(callback).toHaveBeenCalledTimes(1);
  observers[1].emit(node, false);
  expect(callback).toHaveBeenLastCalledWith(false);
  third();
  expect(observers[1].disconnect).toHaveBeenCalledTimes(1);
});
