/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "./invariant";
import { clamp } from "./math";

export function arrayDelete<T>(array: T[], index: number): T[] {
  return [...array.slice(0, index), ...array.slice(index + 1)];
}

export function arrayInsert<T>(array: T[], index: number, value: T): T[] {
  index = clamp(index, 0, array.length);
  return arrayInsertMany(array, index, [value]);
}

export function arrayMove<T>(array: T[], from: number, to: number): T[] {
  const value = array[from];
  return arrayInsertMany(arrayDelete(array, from), to, [value]);
}

export function arrayInsertMany<T>(
  array: T[],
  index: number,
  values: T[],
): T[] {
  if (array.length === 0) {
    return values;
  }
  // Clamp index to the end of the array
  index = clamp(index, 0, array.length);
  return [...array.slice(0, index), ...values, ...array.slice(index)];
}

export function arrayShallowEquals<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  for (let i = 0, l = a.length; i < l; i++) {
    if (a[i] !== b[i]) {
      return false;
    }
  }
  return true;
}

export const Arrays = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  EMPTY: [] as any[],
  zip: <T, U>(a: T[], b: U[]): Array<[T, U]> => {
    invariant(a.length === b.length, "Arrays must be the same length");
    const result: Array<[T, U]> = [];
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      result.push([a[i], b[i]]);
    }
    return result;
  },
};

export function arrayToggle<T>(arr: T[], item: T): T[] {
  if (!arr) {
    return [item];
  }
  return arr.includes(item) ? arr.filter((i) => i !== item) : [...arr, item];
}
