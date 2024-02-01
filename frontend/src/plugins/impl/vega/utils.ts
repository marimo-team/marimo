/* Copyright 2024 Marimo. All rights reserved. */
export function mergeAsArrays<T>(
  left: T | T[] | undefined,
  right: T | T[] | undefined,
): T[] {
  return [...toArray(left), ...toArray(right)];
}

function toArray<T>(value: T | T[] | undefined): T[] {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value;
  }
  return [value];
}
