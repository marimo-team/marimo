/* Copyright 2023 Marimo. All rights reserved. */
export function arrayDelete<T>(array: T[], index: number): T[] {
  return [...array.slice(0, index), ...array.slice(index + 1)];
}

export function arrayInsert<T>(array: T[], index: number, value: T): T[] {
  if (array.length === 0) {
    return [value];
  }

  return [...array.slice(0, index), value, ...array.slice(index)];
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
};
