/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { Deferred } from "../Deferred";
import { mapWithConcurrency, Semaphore } from "../semaphore";

describe("Semaphore", () => {
  it("rejects invalid permit counts", () => {
    expect(() => new Semaphore(0)).toThrow();
    expect(() => new Semaphore(-1)).toThrow();
    expect(() => new Semaphore(1.5)).toThrow();
  });

  it("resolves run() with the function's value", async () => {
    const sem = new Semaphore(1);
    await expect(sem.run(async () => 42)).resolves.toBe(42);
    expect(sem.available).toBe(1);
    expect(sem.pending).toBe(0);
  });

  it("releases the permit when run() rejects", async () => {
    const sem = new Semaphore(1);
    await expect(
      sem.run(async () => {
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    expect(sem.available).toBe(1);
  });

  it("caps concurrent in-flight tasks at `permits`", async () => {
    const sem = new Semaphore(3);
    let inFlight = 0;
    let maxInFlight = 0;
    const gates = Array.from({ length: 10 }, () => new Deferred<void>());

    const tasks = gates.map((gate) =>
      sem.run(async () => {
        inFlight++;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await gate.promise;
        inFlight--;
      }),
    );

    // Let microtasks run so the first batch is scheduled.
    await Promise.resolve();
    await Promise.resolve();

    expect(maxInFlight).toBe(3);
    expect(sem.available).toBe(0);
    expect(sem.pending).toBe(7);

    // Release them all and confirm everyone finishes.
    for (const gate of gates) {
      gate.resolve();
    }
    await Promise.all(tasks);
    expect(maxInFlight).toBe(3);
    expect(sem.available).toBe(3);
    expect(sem.pending).toBe(0);
  });

  it("releases waiters in FIFO order", async () => {
    const sem = new Semaphore(1);
    const order: number[] = [];
    const hold = new Deferred<void>();

    // First holder takes the only permit and parks on `hold`.
    const first = sem.run(async () => {
      order.push(0);
      await hold.promise;
    });

    // Queue three more in known order.
    const rest = [1, 2, 3].map((i) =>
      sem.run(async () => {
        order.push(i);
      }),
    );

    await Promise.resolve();
    expect(order).toEqual([0]);
    expect(sem.pending).toBe(3);

    hold.resolve();
    await Promise.all([first, ...rest]);
    expect(order).toEqual([0, 1, 2, 3]);
  });

  it("throws on release() beyond initial permit count", () => {
    const sem = new Semaphore(2);
    expect(() => sem.release()).toThrow(/more times than acquire/);
  });

  it("supports manual acquire/release", async () => {
    const sem = new Semaphore(2);
    await sem.acquire();
    await sem.acquire();
    expect(sem.available).toBe(0);

    let resolved = false;
    const waiter = sem.acquire().then(() => {
      resolved = true;
    });
    await Promise.resolve();
    expect(resolved).toBe(false);

    sem.release();
    await waiter;
    expect(resolved).toBe(true);

    sem.release();
    sem.release();
    expect(sem.available).toBe(2);
  });
});

describe("mapWithConcurrency", () => {
  it("returns [] for empty input without invoking fn", async () => {
    let called = 0;
    const result = await mapWithConcurrency([], 5, async () => {
      called++;
      return 1;
    });
    expect(result).toEqual([]);
    expect(called).toBe(0);
  });

  it("preserves input order in the result", async () => {
    const input = [10, 20, 30, 40, 50];
    const result = await mapWithConcurrency(input, 2, async (n) => {
      // Reverse the natural completion order so we'd notice if order broke.
      await new Promise((r) => setTimeout(r, input.length - input.indexOf(n)));
      return n * 2;
    });
    expect(result).toEqual([20, 40, 60, 80, 100]);
  });

  it("respects the concurrency cap", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    const items = Array.from({ length: 20 }, (_, i) => i);
    const gates = items.map(() => new Deferred<void>());

    const result = mapWithConcurrency(items, 4, async (i) => {
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await gates[i].promise;
      inFlight--;
      return i;
    });

    // Flush microtasks so the first batch enters fn().
    await Promise.resolve();
    await Promise.resolve();
    expect(maxInFlight).toBe(4);

    // Releasing one gate should let exactly one queued task enter fn().
    for (const gate of gates) {
      gate.resolve();
    }
    await result;
    expect(maxInFlight).toBe(4);
  });

  it("lets in-flight tasks complete after the first rejection", async () => {
    const completed: number[] = [];
    const gates = [0, 1, 2, 3, 4].map(() => new Deferred<void>());

    const result = mapWithConcurrency([0, 1, 2, 3, 4], 5, async (i) => {
      await gates[i].promise;
      if (i === 0) {
        throw new Error("first failed");
      }
      completed.push(i);
      return i;
    });

    // Reject the first one; the other 4 are still gated.
    gates[0].resolve();
    // Drain the rejection (catch so it doesn't escape the test).
    await expect(result).rejects.toThrow("first failed");

    // The other tasks were already in-flight when the rejection happened;
    // they should still resolve when their gates open.
    for (let i = 1; i < gates.length; i++) {
      gates[i].resolve();
    }
    // Yield so the remaining sem.run() finallys run.
    await new Promise((r) => setTimeout(r, 0));
    expect(completed.toSorted()).toEqual([1, 2, 3, 4]);
  });

  it("rejects on the first error", async () => {
    await expect(
      mapWithConcurrency([1, 2, 3], 2, async (n) => {
        if (n === 2) {
          throw new Error("nope");
        }
        return n;
      }),
    ).rejects.toThrow("nope");
  });

  it("throws on invalid concurrency, even for empty input", () => {
    expect(() => mapWithConcurrency([1, 2, 3], 0, async (n) => n)).toThrow();
    expect(() => mapWithConcurrency([], 0, async (n: number) => n)).toThrow();
  });

  it("passes the index to fn", async () => {
    const result = await mapWithConcurrency(
      ["a", "b", "c"],
      2,
      async (item, index) => `${index}:${item}`,
    );
    expect(result).toEqual(["0:a", "1:b", "2:c"]);
  });
});
