/* Copyright 2026 Marimo. All rights reserved. */

import { arrayShallowEquals } from "./arrays";

export function once<Args extends unknown[], Result, This>(
  fn: (this: This, ...args: Args) => Result,
): (this: This, ...args: Args) => Result {
  let result: Result;
  let called = false;
  return function (this: This, ...args: Args): Result {
    if (!called) {
      called = true;
      result = fn.apply(this, args);
    }
    return result;
  };
}

export function memoizeLastValue<Args extends unknown[], Result, This>(
  fn: (this: This, ...args: Args) => Result,
): (this: This, ...args: Args) => Result {
  let result: Result;
  let lastArgs: Args | undefined;
  let lastError: unknown;
  let hasError = false;

  return function (this: This, ...args: Args): Result {
    if (lastArgs === undefined || !arrayShallowEquals(args, lastArgs)) {
      try {
        result = fn.apply(this, args);
        hasError = false;
        lastError = undefined;
      } catch (error) {
        hasError = true;
        lastError = error;
      }
      lastArgs = args;
    }

    if (hasError) {
      throw lastError;
    }
    return result;
  };
}
