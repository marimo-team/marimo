/* Copyright 2026 Marimo. All rights reserved. */

import { Deferred } from "./Deferred";

/**
 * Handle returned by {@link AsyncCaptureTracker.startCapture}.
 *
 * The handle is scoped to one capture attempt. If the same key is re-captured
 * before this handle completes, calling `markCaptured` or `markFailed` on
 * the stale handle is a safe no-op.
 */
export interface CaptureHandle<R> {
  /** Per-key AbortSignal — check between async steps. */
  readonly signal: AbortSignal;
  /** Mark the capture as successful and resolve waiters with the result. */
  markCaptured(result: R): void;
  /** Mark the capture as failed — the key returns to idle for retry. */
  markFailed(): void;
}

interface InFlightEntry<R> {
  controller: AbortController;
  inputValue: unknown;
  deferred: Deferred<R | undefined>;
}

/**
 * Tracks async capture operations to prevent race conditions.
 *
 * Each key transitions through states:
 * - **idle**: Not captured or previously failed — eligible for capture
 * - **in-flight**: Capture started but not completed — skipped unless value changed
 * - **captured(value)**: Successfully captured — skipped until value changes
 *
 * Abort is per-key: aborting one key's in-flight capture does not affect others.
 *
 * Guarantees:
 * - Items are only marked "captured" after successful async completion
 * - In-flight items with the same value are skipped (prevents duplicates)
 * - In-flight items whose value changed are aborted and re-captured
 * - Failed items return to idle (retried next cycle)
 * - Concurrent callers can await an in-flight capture via {@link waitForInFlight}
 * - Stale handles are safe no-ops (checked via entry identity)
 */
export class AsyncCaptureTracker<K, R = unknown> {
  /** Input values for successfully captured keys */
  private capturedInputs = new Map<K, unknown>();
  /** Per-key in-flight state */
  private inFlight = new Map<K, InFlightEntry<R>>();

  /** Abort an in-flight entry and resolve its waiters with `undefined`. */
  private cancelEntry(entry: InFlightEntry<R>): void {
    entry.controller.abort();
    if (entry.deferred.status === "pending") {
      entry.deferred.resolve(undefined);
    }
  }

  /**
   * Whether a key needs capturing based on its current input value.
   * Returns false if:
   * - Already captured with the same value
   * - In-flight with the same value (let it finish — use {@link waitForInFlight} to get the result)
   * Returns true if:
   * - Never captured
   * - Captured with a different value
   * - In-flight with a different value (will be aborted on {@link startCapture})
   */
  needsCapture(key: K, inputValue: unknown): boolean {
    if (this.capturedInputs.get(key) === inputValue) {
      return false;
    }
    const flight = this.inFlight.get(key);
    if (flight && flight.inputValue === inputValue) {
      return false;
    }
    return true;
  }

  /**
   * If the key is in-flight with the given input value, returns a promise
   * that resolves when the capture completes (with the result, or `undefined`
   * on failure/abort). Returns `null` otherwise.
   */
  waitForInFlight(key: K, inputValue: unknown): Promise<R | undefined> | null {
    const flight = this.inFlight.get(key);
    if (flight && flight.inputValue === inputValue) {
      return flight.deferred.promise;
    }
    return null;
  }

  /**
   * Start capturing a single key. If the key is already in-flight,
   * aborts only that key's previous capture and resolves its waiters
   * with `undefined`.
   *
   * @returns A {@link CaptureHandle} scoped to this attempt.
   */
  startCapture(key: K, inputValue: unknown): CaptureHandle<R> {
    const prev = this.inFlight.get(key);
    if (prev) {
      this.cancelEntry(prev);
    }

    const controller = new AbortController();
    const deferred = new Deferred<R | undefined>();
    const entry: InFlightEntry<R> = { controller, inputValue, deferred };
    this.inFlight.set(key, entry);

    return {
      signal: controller.signal,
      markCaptured: (result: R) => {
        // No-op if this handle was superseded by a newer startCapture
        if (this.inFlight.get(key) !== entry) {
          return;
        }
        deferred.resolve(result);
        this.capturedInputs.set(key, inputValue);
        this.inFlight.delete(key);
      },
      markFailed: () => {
        if (this.inFlight.get(key) !== entry) {
          return;
        }
        deferred.resolve(undefined);
        this.inFlight.delete(key);
      },
    };
  }

  /**
   * Remove tracking for keys not in the given set.
   * Aborts in-flight captures and resolves their waiters with `undefined`.
   */
  prune(currentKeys: Set<K>): void {
    for (const key of this.capturedInputs.keys()) {
      if (!currentKeys.has(key)) {
        this.capturedInputs.delete(key);
      }
    }
    for (const [key, entry] of this.inFlight) {
      if (!currentKeys.has(key)) {
        this.cancelEntry(entry);
        this.inFlight.delete(key);
      }
    }
  }

  /** Whether any captures are currently in-flight. */
  get isCapturing(): boolean {
    return this.inFlight.size > 0;
  }

  /** Abort all in-flight captures. Resolves all waiters with `undefined`. */
  abort(): void {
    for (const entry of this.inFlight.values()) {
      this.cancelEntry(entry);
    }
    this.inFlight.clear();
  }

  /** Reset all state. */
  reset(): void {
    this.abort();
    this.capturedInputs.clear();
  }
}
