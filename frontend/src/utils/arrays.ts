/* Copyright 2023 Marimo. All rights reserved. */
export function arrayDelete<T>(array: T[], index: number): T[] {
  return [...array.slice(0, index), ...array.slice(index + 1)];
}

export function arrayInsert<T>(array: T[], index: number, value: T): T[] {
  return [...array.slice(0, index), value, ...array.slice(index)];
}

export const Arrays = {
  EMPTY: [] as any[],
};
