/* Copyright 2024 Marimo. All rights reserved. */
export function once<T extends (...args: unknown[]) => unknown>(fn: T): T {
  let result: ReturnType<T>;
  let called = false;
  return function (
    this: ThisParameterType<T>,
    ...args: Parameters<T>
  ): ReturnType<T> {
    if (!called) {
      called = true;
      result = fn.apply(this, args) as ReturnType<T>;
    }
    return result;
  } as T;
}
