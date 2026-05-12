/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Counting semaphore that gates async work to at most `permits` in-flight
 * tasks. Waiters are released in FIFO order.
 */
export class Semaphore {
  private readonly maxPermits: number;
  private permits: number;
  private waiters: Array<() => void> = [];

  constructor(permits: number) {
    if (!Number.isInteger(permits) || permits < 1) {
      throw new Error(
        `Semaphore permits must be a positive integer, got ${permits}`,
      );
    }
    this.maxPermits = permits;
    this.permits = permits;
  }

  /** Permits currently available. */
  get available(): number {
    return this.permits;
  }

  /** Number of waiters queued for a permit. */
  get pending(): number {
    return this.waiters.length;
  }

  acquire(): Promise<void> {
    if (this.permits > 0) {
      this.permits--;
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      this.waiters.push(resolve);
    });
  }

  release(): void {
    const next = this.waiters.shift();
    if (next) {
      next();
      return;
    }
    if (this.permits >= this.maxPermits) {
      throw new Error(
        "Semaphore.release() called more times than acquire() — refusing to exceed initial permit count",
      );
    }
    this.permits++;
  }

  /** Acquire a permit, run `fn`, then release the permit. */
  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }
}

/**
 * Map over `items` with bounded parallelism. Preserves input order in the
 * result. Rejects as soon as the first task rejects (like `Promise.all`);
 * already-started tasks keep running to completion in the background but
 * their results are dropped.
 */
// oxlint-disable-next-line marimo/prefer-object-params -- map-style helper, mirrors Array.prototype.map
export function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  // Validate concurrency before the empty-input fast path so misconfiguration
  // is never silently accepted.
  const sem = new Semaphore(concurrency);
  if (items.length === 0) {
    return Promise.resolve([]);
  }
  return Promise.all(
    items.map((item, index) => sem.run(() => fn(item, index))),
  );
}
