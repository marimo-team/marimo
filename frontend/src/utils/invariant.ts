/* Copyright 2024 Marimo. All rights reserved. */
export function invariant(
  condition: boolean,
  message: string,
): asserts condition;
export function invariant<T>(
  condition: T,
  message: string,
): asserts condition is NonNullable<T>;
export function invariant(
  condition: boolean,
  message: string,
): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}
