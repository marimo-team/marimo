/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "./invariant";
import { clamp } from "./math";

export function arrayDelete<T>(array: T[], index: number): T[] {
  const result = [...array];
  result.splice(index, 1);
  return result;
}

export function arrayInsert<T>(array: T[], index: number, value: T): T[] {
  index = clamp(index, 0, array.length);
  const result = [...array];
  result.splice(index, 0, value);
  return result;
}

export function arrayMove<T>(array: T[], from: number, to: number): T[] {
  const result = [...array];
  const [value] = result.splice(from, 1);
  result.splice(to, 0, value);
  return result;
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
  const result = [...array];
  result.splice(index, 0, ...values);
  return result;
}

export function arrayShallowEquals<T>(a: T[], b: T[]): boolean {
  if (a === b) {
    return true;
  }
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
  EMPTY: [] as any,
  zip: <T, U>(a: T[], b: U[]): Array<[T, U]> => {
    invariant(a.length === b.length, "Arrays must be the same length");
    return a.map((item, i) => [item, b[i]]);
  },
};

export function arrayToggle<T>(arr: T[], item: T): T[] {
  if (!arr) {
    return [item];
  }
  const index = arr.indexOf(item);
  if (index === -1) {
    return [...arr, item];
  }
  const result = [...arr];
  result.splice(index, 1);
  return result;
}
