/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  createSharedResource,
  createSharedSubscription,
} from "../shared-resource";

describe("shared resources", () => {
  it.each([1, 500])(
    "keeps one resource for %i consumers and supports remounting",
    (count) => {
      const stop = vi.fn();
      const start = vi.fn(() => stop);
      const acquire = createSharedResource(start);
      const releases = Array.from({ length: count }, acquire);
      expect(start).toHaveBeenCalledTimes(1);
      for (const release of releases.slice(1)) {
        release();
        release();
      }
      expect(stop).not.toHaveBeenCalled();
      releases[0]();
      releases[0]();
      expect(stop).toHaveBeenCalledTimes(1);
      const release = acquire();
      expect(start).toHaveBeenCalledTimes(2);
      release();
      expect(stop).toHaveBeenCalledTimes(2);
    },
  );

  it("can retry if starting the resource fails", () => {
    const stop = vi.fn();
    const acquire = createSharedResource(
      vi
        .fn()
        .mockImplementationOnce(() => {
          throw new Error("start failed");
        })
        .mockReturnValue(stop),
    );
    expect(acquire).toThrow("start failed");
    acquire()();
    expect(stop).toHaveBeenCalledOnce();
  });

  it("keeps duplicate subscriptions independent", () => {
    let notify: () => void = vi.fn();
    const stop = vi.fn();
    const subscribe = createSharedSubscription((onChange) => {
      notify = onChange;
      return stop;
    });
    const listener = vi.fn();
    const first = subscribe(listener);
    const second = subscribe(listener);
    notify();
    expect(listener).toHaveBeenCalledTimes(2);
    first();
    first();
    notify();
    expect(listener).toHaveBeenCalledTimes(3);
    expect(stop).not.toHaveBeenCalled();
    second();
    notify();
    expect(listener).toHaveBeenCalledTimes(3);
    expect(stop).toHaveBeenCalledOnce();
  });
  it("does not notify subscribers added during the same notification", () => {
    let notify: () => void = vi.fn();
    const subscribe = createSharedSubscription((onChange) => {
      notify = onChange;
      return vi.fn();
    });
    const second = vi.fn();
    let releaseSecond: () => void = vi.fn();
    const releaseFirst = subscribe(() => {
      releaseSecond = subscribe(second);
    });
    notify();
    expect(second).not.toHaveBeenCalled();
    releaseFirst();
    notify();
    expect(second).toHaveBeenCalledOnce();
    releaseSecond();
  });

  it("delivers synchronous notifications and rolls back failed subscriptions", () => {
    const stop = vi.fn();
    const start = vi.fn((notify: () => void) => {
      notify();
      return stop;
    });
    start.mockImplementationOnce(() => {
      throw new Error("start failed");
    });
    const subscribe = createSharedSubscription(start);
    const failed = vi.fn();
    expect(() => subscribe(failed)).toThrow("start failed");
    const listener = vi.fn();
    const release = subscribe(listener);
    expect(listener).toHaveBeenCalledOnce();
    expect(failed).not.toHaveBeenCalled();
    release();
    expect(stop).toHaveBeenCalledOnce();
  });
});
