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
  zip: <T, U>(a: T[], b: U[]): [T, U][] => {
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

export function uniqueBy<T>(arr: T[], key: (item: T) => string): T[] {
  const result = [];
  const seen = new Set();
  for (const item of arr) {
    const k = key(item);
    if (!seen.has(k)) {
      seen.add(k);
      result.push(item);
    }
  }
  return result;
}

/**
 * Get the next index in the list, wrapping around to the start or end if necessary.
 * @param currentIndex - The current index, or null if there is no current index.
 * @param listLength - The length of the list.
 * @param direction - The direction to move in.
 * @returns The next index.
 */
export function getNextIndex(
  currentIndex: number | null,
  listLength: number,
  direction: "up" | "down",
): number {
  if (listLength === 0) {
    return 0;
  }

  if (currentIndex === null) {
    return direction === "up" ? 0 : listLength - 1;
  }

  return direction === "up"
    ? (currentIndex + 1) % listLength
    : (currentIndex - 1 + listLength) % listLength;
}
