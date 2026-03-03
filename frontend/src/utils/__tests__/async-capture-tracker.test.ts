/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it } from "vitest";
import { AsyncCaptureTracker } from "../async-capture-tracker";

describe("AsyncCaptureTracker", () => {
  let tracker: AsyncCaptureTracker<string, string>;

  beforeEach(() => {
    tracker = new AsyncCaptureTracker();
  });

  describe("needsCapture", () => {
    it("should return true for keys not yet captured", () => {
      expect(tracker.needsCapture("a", "value1")).toBe(true);
    });

    it("should return false for keys captured with the same value", () => {
      const handle = tracker.startCapture("a", "value1");
      handle.markCaptured("result");
      expect(tracker.needsCapture("a", "value1")).toBe(false);
    });

    it("should return true for keys captured with a different value", () => {
      const handle = tracker.startCapture("a", "value1");
      handle.markCaptured("result");
      expect(tracker.needsCapture("a", "value2")).toBe(true);
    });

    it("should return false for keys in-flight with the same value", () => {
      tracker.startCapture("a", "value1");
      expect(tracker.needsCapture("a", "value1")).toBe(false);
    });

    it("should return true for keys in-flight with a different value", () => {
      tracker.startCapture("a", "value1");
      expect(tracker.needsCapture("a", "value2")).toBe(true);
    });

    it("should return true for keys that failed (returned to idle)", () => {
      const handle = tracker.startCapture("a", "value1");
      handle.markFailed();
      expect(tracker.needsCapture("a", "value1")).toBe(true);
    });
  });

  describe("startCapture", () => {
    it("should return a handle with a non-aborted signal", () => {
      const handle = tracker.startCapture("a", "v");
      expect(handle.signal.aborted).toBe(false);
    });

    it("should abort only the same key's previous signal", () => {
      const handleA = tracker.startCapture("a", "v1");
      const handleB = tracker.startCapture("b", "v1");
      const handleA2 = tracker.startCapture("a", "v2");

      expect(handleA.signal.aborted).toBe(true);
      expect(handleB.signal.aborted).toBe(false);
      expect(handleA2.signal.aborted).toBe(false);

      // Unrelated key still completes independently
      handleB.markCaptured("result-b");
      expect(tracker.needsCapture("b", "v1")).toBe(false);
    });

    it("should not abort other keys when one is re-captured", () => {
      tracker.startCapture("a", "v");
      tracker.startCapture("b", "v");
      tracker.startCapture("c", "v");

      const handleB2 = tracker.startCapture("b", "v2");

      expect(tracker.needsCapture("a", "v")).toBe(false); // still in-flight
      expect(tracker.needsCapture("c", "v")).toBe(false); // still in-flight
      expect(handleB2.signal.aborted).toBe(false);
    });

    it("should mark key as in-flight", () => {
      tracker.startCapture("a", "v");
      expect(tracker.isCapturing).toBe(true);
      expect(tracker.needsCapture("a", "v")).toBe(false);
    });
  });

  describe("handle.markCaptured", () => {
    it("should remove key from in-flight", () => {
      const handle = tracker.startCapture("a", "v");
      expect(tracker.isCapturing).toBe(true);
      handle.markCaptured("result");
      expect(tracker.isCapturing).toBe(false);
    });

    it("should persist the captured value", () => {
      const handle = tracker.startCapture("a", "value1");
      handle.markCaptured("result");
      expect(tracker.needsCapture("a", "value1")).toBe(false);
      expect(tracker.needsCapture("a", "value2")).toBe(true);
    });

    it("should update the captured value on re-capture", () => {
      const h1 = tracker.startCapture("a", "v1");
      h1.markCaptured("r1");

      const h2 = tracker.startCapture("a", "v2");
      h2.markCaptured("r2");

      expect(tracker.needsCapture("a", "v1")).toBe(true);
      expect(tracker.needsCapture("a", "v2")).toBe(false);
    });

    it("should be a no-op when handle is stale (superseded)", () => {
      const handle1 = tracker.startCapture("a", "v1");
      const handle2 = tracker.startCapture("a", "v2");

      // handle1 is stale — markCaptured should not affect state
      handle1.markCaptured("stale-result");

      // "a" should still be in-flight with v2
      expect(tracker.needsCapture("a", "v2")).toBe(false); // in-flight
      expect(tracker.needsCapture("a", "v1")).toBe(true); // not captured
      expect(tracker.isCapturing).toBe(true);

      // handle2 still works
      handle2.markCaptured("real-result");
      expect(tracker.needsCapture("a", "v2")).toBe(false); // captured
      expect(tracker.isCapturing).toBe(false);
    });
  });

  describe("handle.markFailed", () => {
    it("should remove key from in-flight", () => {
      const handle = tracker.startCapture("a", "v");
      handle.markFailed();
      expect(tracker.isCapturing).toBe(false);
    });

    it("should not add a captured entry", () => {
      const handle = tracker.startCapture("a", "v");
      handle.markFailed();
      expect(tracker.needsCapture("a", "v")).toBe(true);
    });

    it("should not clear a previously captured value", () => {
      const h1 = tracker.startCapture("a", "v1");
      h1.markCaptured("r1");

      const h2 = tracker.startCapture("a", "v2");
      h2.markFailed();

      expect(tracker.needsCapture("a", "v1")).toBe(false);
      expect(tracker.needsCapture("a", "v2")).toBe(true);
    });

    it("should be a no-op when handle is stale", () => {
      const handle1 = tracker.startCapture("a", "v1");
      tracker.startCapture("a", "v2");

      handle1.markFailed();

      // "a" should still be in-flight with v2
      expect(tracker.isCapturing).toBe(true);
      expect(tracker.needsCapture("a", "v2")).toBe(false);
    });
  });

  describe("waitForInFlight", () => {
    it("should return a promise for in-flight key with same value", async () => {
      const handle = tracker.startCapture("a", "v1");
      const promise = tracker.waitForInFlight("a", "v1");
      expect(promise).not.toBeNull();

      handle.markCaptured("result-a");
      const result = await promise;
      expect(result).toBe("result-a");
    });

    it("should return null for captured key (not in-flight)", () => {
      const handle = tracker.startCapture("a", "v1");
      handle.markCaptured("result");
      expect(tracker.waitForInFlight("a", "v1")).toBeNull();
    });

    it("should return null for key not being tracked", () => {
      expect(tracker.waitForInFlight("a", "v1")).toBeNull();
    });

    it("should return null for in-flight key with different value", () => {
      tracker.startCapture("a", "v1");
      expect(tracker.waitForInFlight("a", "v2")).toBeNull();
    });

    it("should resolve with undefined when capture fails", async () => {
      const handle = tracker.startCapture("a", "v1");
      const promise = tracker.waitForInFlight("a", "v1");

      handle.markFailed();
      const result = await promise;
      expect(result).toBeUndefined();
    });

    it("should resolve with undefined when capture is superseded", async () => {
      tracker.startCapture("a", "v1");
      const promise = tracker.waitForInFlight("a", "v1");

      // Supersede with new capture
      tracker.startCapture("a", "v2");
      const result = await promise;
      expect(result).toBeUndefined();
    });

    it("should resolve with undefined when aborted", async () => {
      tracker.startCapture("a", "v1");
      const promise = tracker.waitForInFlight("a", "v1");

      tracker.abort();
      const result = await promise;
      expect(result).toBeUndefined();
    });

    it("should allow multiple waiters on the same key", async () => {
      const handle = tracker.startCapture("a", "v1");
      const p1 = tracker.waitForInFlight("a", "v1");
      const p2 = tracker.waitForInFlight("a", "v1");

      handle.markCaptured("shared-result");

      const [r1, r2] = await Promise.all([p1, p2]);
      expect(r1).toBe("shared-result");
      expect(r2).toBe("shared-result");
    });
  });

  describe("prune", () => {
    it("should remove captured entries for keys not in the set", () => {
      const hA = tracker.startCapture("a", "v1");
      hA.markCaptured("r1");
      const hB = tracker.startCapture("b", "v2");
      hB.markCaptured("r2");

      tracker.prune(new Set(["a"]));

      expect(tracker.needsCapture("a", "v1")).toBe(false);
      expect(tracker.needsCapture("b", "v2")).toBe(true);
    });

    it("should abort and remove in-flight entries for pruned keys", () => {
      const handleA = tracker.startCapture("a", "v");
      const handleB = tracker.startCapture("b", "v");

      tracker.prune(new Set(["a"]));

      expect(handleA.signal.aborted).toBe(false);
      expect(handleB.signal.aborted).toBe(true);
      expect(tracker.needsCapture("b", "v")).toBe(true);
    });

    it("should resolve pruned in-flight deferreds with undefined", async () => {
      tracker.startCapture("b", "v");
      const promise = tracker.waitForInFlight("b", "v");

      tracker.prune(new Set(["a"]));
      const result = await promise;
      expect(result).toBeUndefined();
    });

    it("should do nothing if all keys are current", () => {
      const hA = tracker.startCapture("a", "v1");
      hA.markCaptured("r1");
      const hB = tracker.startCapture("b", "v2");
      hB.markCaptured("r2");

      tracker.prune(new Set(["a", "b"]));

      expect(tracker.needsCapture("a", "v1")).toBe(false);
      expect(tracker.needsCapture("b", "v2")).toBe(false);
    });
  });

  describe("abort", () => {
    it("should abort all in-flight signals", () => {
      const handleA = tracker.startCapture("a", "v");
      const handleB = tracker.startCapture("b", "v");
      tracker.abort();
      expect(handleA.signal.aborted).toBe(true);
      expect(handleB.signal.aborted).toBe(true);
    });

    it("should clear in-flight state", () => {
      tracker.startCapture("a", "v");
      tracker.abort();
      expect(tracker.isCapturing).toBe(false);
      expect(tracker.needsCapture("a", "v")).toBe(true);
    });

    it("should not clear captured state", () => {
      const handle = tracker.startCapture("a", "v1");
      handle.markCaptured("result");
      tracker.abort();
      expect(tracker.needsCapture("a", "v1")).toBe(false);
    });
  });

  describe("reset", () => {
    it("should clear all state", () => {
      const hA = tracker.startCapture("a", "v1");
      hA.markCaptured("r1");
      tracker.startCapture("b", "v2");

      tracker.reset();

      expect(tracker.isCapturing).toBe(false);
      expect(tracker.needsCapture("a", "v1")).toBe(true);
      expect(tracker.needsCapture("b", "v2")).toBe(true);
    });
  });

  describe("isCapturing", () => {
    it("should be false when nothing is in-flight", () => {
      expect(tracker.isCapturing).toBe(false);
    });

    it("should be true when items are in-flight", () => {
      tracker.startCapture("a", "v");
      expect(tracker.isCapturing).toBe(true);
    });

    it("should be false when all items are completed", () => {
      const hA = tracker.startCapture("a", "v");
      const hB = tracker.startCapture("b", "v");
      hA.markCaptured("r");
      hB.markFailed();
      expect(tracker.isCapturing).toBe(false);
    });
  });

  describe("granular abort", () => {
    it("should allow independent completion of unrelated keys", () => {
      const hA = tracker.startCapture("a", "v1");
      tracker.startCapture("b", "v1");
      const hC = tracker.startCapture("c", "v1");

      hA.markCaptured("ra");
      tracker.startCapture("b", "v2"); // abort old "b", start new
      hC.markCaptured("rc");

      expect(tracker.needsCapture("a", "v1")).toBe(false);
      expect(tracker.needsCapture("c", "v1")).toBe(false);
      expect(tracker.needsCapture("b", "v2")).toBe(false); // in-flight
      expect(tracker.needsCapture("b", "v1")).toBe(true);
    });
  });
});
