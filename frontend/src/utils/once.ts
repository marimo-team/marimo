/* Copyright 2024 Marimo. All rights reserved. */

import { arrayShallowEquals } from "./arrays";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function once<T extends (...args: any[]) => any>(fn: T): T {
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

export function memoizeLastValue<T extends (...args: any[]) => any>(fn: T): T {
  let result: ReturnType<T>;
  let lastArgs: Parameters<T> | undefined;
  let lastError: any;
  let hasError = false;

  return function (
    this: ThisParameterType<T>,
    ...args: Parameters<T>
  ): ReturnType<T> {
    if (lastArgs === undefined || !arrayShallowEquals(args, lastArgs)) {
      try {
        result = fn.apply(this, args) as ReturnType<T>;
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
  } as T;
}
