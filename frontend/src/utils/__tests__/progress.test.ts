/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { ProgressState } from "../progress";

describe("ProgressState", () => {
  describe("constructor", () => {
    it("should initialize with a numeric total", () => {
      const progress = new ProgressState(100);
      expect(progress.getProgress()).toBe(0);
    });

    it("should initialize with indeterminate total", () => {
      const progress = new ProgressState("indeterminate");
      expect(progress.getProgress()).toBe("indeterminate");
    });
  });

  describe("static indeterminate", () => {
    it("should create an indeterminate progress state", () => {
      const progress = ProgressState.indeterminate();
      expect(progress.getProgress()).toBe("indeterminate");
    });
  });

  describe("addTotal", () => {
    it("should add to the total when numeric", () => {
      const progress = new ProgressState(100);
      progress.addTotal(50);
      // Progress is 0, total is now 150
      expect(progress.getProgress()).toBe(0);
      progress.increment(75);
      expect(progress.getProgress()).toBe(50); // 75/150 * 100 = 50
    });

    it("should convert indeterminate to numeric when adding total", () => {
      const progress = ProgressState.indeterminate();
      expect(progress.getProgress()).toBe("indeterminate");
      progress.addTotal(100);
      expect(progress.getProgress()).toBe(0);
    });
  });

  describe("increment", () => {
    it("should increment the progress", () => {
      const progress = new ProgressState(100);
      progress.increment(25);
      expect(progress.getProgress()).toBe(25);
    });

    it("should accumulate multiple increments", () => {
      const progress = new ProgressState(100);
      progress.increment(25);
      progress.increment(25);
      progress.increment(25);
      expect(progress.getProgress()).toBe(75);
    });

    it("should allow progress beyond 100%", () => {
      const progress = new ProgressState(100);
      progress.increment(150);
      expect(progress.getProgress()).toBe(150);
    });
  });

  describe("getProgress", () => {
    it("should return indeterminate for indeterminate state", () => {
      const progress = ProgressState.indeterminate();
      progress.increment(50); // increment has no visible effect
      expect(progress.getProgress()).toBe("indeterminate");
    });

    it("should return correct percentage", () => {
      const progress = new ProgressState(200);
      progress.increment(50);
      expect(progress.getProgress()).toBe(25); // 50/200 * 100 = 25
    });

    it("should return 0 when no progress made", () => {
      const progress = new ProgressState(100);
      expect(progress.getProgress()).toBe(0);
    });

    it("should return 100 when complete", () => {
      const progress = new ProgressState(100);
      progress.increment(100);
      expect(progress.getProgress()).toBe(100);
    });
  });

  describe("subscribe", () => {
    it("should notify listeners on increment", () => {
      const progress = new ProgressState(100);
      const listener = vi.fn();
      progress.subscribe(listener);

      progress.increment(25);
      expect(listener).toHaveBeenCalledWith(25);

      progress.increment(25);
      expect(listener).toHaveBeenCalledWith(50);
      expect(listener).toHaveBeenCalledTimes(2);
    });

    it("should notify listeners on addTotal", () => {
      const progress = new ProgressState(100);
      const listener = vi.fn();
      progress.subscribe(listener);

      progress.addTotal(100);
      expect(listener).toHaveBeenCalledWith(0); // 0/200 = 0%
    });

    it("should notify listeners when converting from indeterminate", () => {
      const progress = ProgressState.indeterminate();
      const listener = vi.fn();
      progress.subscribe(listener);

      progress.addTotal(100);
      expect(listener).toHaveBeenCalledWith(0);
    });

    it("should return unsubscribe function", () => {
      const progress = new ProgressState(100);
      const listener = vi.fn();
      const unsubscribe = progress.subscribe(listener);

      progress.increment(25);
      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();
      progress.increment(25);
      expect(listener).toHaveBeenCalledTimes(1); // no additional calls
    });

    it("should support multiple listeners", () => {
      const progress = new ProgressState(100);
      const listener1 = vi.fn();
      const listener2 = vi.fn();
      progress.subscribe(listener1);
      progress.subscribe(listener2);

      progress.increment(50);
      expect(listener1).toHaveBeenCalledWith(50);
      expect(listener2).toHaveBeenCalledWith(50);
    });

    it("should pass indeterminate to listeners", () => {
      const progress = ProgressState.indeterminate();
      const listener = vi.fn();
      progress.subscribe(listener);

      progress.increment(50);
      expect(listener).toHaveBeenCalledWith("indeterminate");
    });
  });
});
