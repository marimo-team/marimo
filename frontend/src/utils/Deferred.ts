/* Copyright 2026 Marimo. All rights reserved. */

/**
 * A deferred promise that can be resolved or rejected externally.
 *
 * Provides synchronous access to status and resolved value, useful for
 * cases where you need to check if a promise has settled without awaiting it.
 */
export class Deferred<T> {
  promise: Promise<T>;
  resolve!: (value: T | PromiseLike<T>) => void;
  reject!: (reason?: unknown) => void;
  status: "pending" | "resolved" | "rejected" = "pending";
  value: T | undefined = undefined;

  constructor() {
    this.promise = new Promise<T>((resolve, reject) => {
      this.reject = (reason: unknown) => {
        this.status = "rejected";
        reject(reason as Error);
      };
      this.resolve = (value) => {
        this.status = "resolved";
        // Store the value for synchronous access
        if (!isPromiseLike(value)) {
          this.value = value;
        }
        resolve(value);
      };
    });
  }
}

function isPromiseLike(value: unknown): value is PromiseLike<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    "then" in value &&
    typeof value.then === "function"
  );
}
