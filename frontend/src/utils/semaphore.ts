/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Counting semaphore that gates async work to at most `permits` in-flight
 * tasks. Waiters are released in FIFO order.
 */
export class Semaphore {
  private permits: number;
  private waiters: Array<() => void> = [];

  constructor(permits: number) {
    if (!Number.isInteger(permits) || permits < 1) {
      throw new Error(
        `Semaphore permits must be a positive integer, got ${permits}`,
      );
    }
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
 * result. Rejects with the first error encountered (like `Promise.all`); other
 * in-flight tasks are awaited but their results are discarded.
 */
// oxlint-disable-next-line marimo/prefer-object-params -- map-style helper, mirrors Array.prototype.map
export function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  if (items.length === 0) {
    return Promise.resolve([]);
  }
  const sem = new Semaphore(concurrency);
  return Promise.all(
    items.map((item, index) => sem.run(() => fn(item, index))),
  );
}
