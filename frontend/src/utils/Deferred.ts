/* Copyright 2024 Marimo. All rights reserved. */
export class Deferred<T> {
  promise: Promise<T>;
  resolve!: (value: T | PromiseLike<T>) => void;
  reject!: (reason?: unknown) => void;
  status: "pending" | "resolved" | "rejected" = "pending";

  constructor() {
    this.promise = new Promise<T>((resolve, reject) => {
      this.reject = (reason: unknown) => {
        this.status = "rejected";
        reject(reason as Error);
      };
      this.resolve = (value) => {
        this.status = "resolved";
        resolve(value);
      };
    });
  }
}
