/* Copyright 2026 Marimo. All rights reserved. */
export const Sets = {
  /**
   * Merge multiple iterables into a single set.
   */
  merge<T>(...sets: Iterable<T>[]): Set<T> {
    const result = new Set<T>();
    for (const set of sets) {
      for (const item of set) {
        result.add(item);
      }
    }
    return result;
  },

  /**
   * Check if two sets are equal (contain the same elements).
   */
  equals<T>(set1: Set<T>, set2: Set<T>): boolean {
    if (set1.size !== set2.size) {
      return false;
    }
    for (const item of set1) {
      if (!set2.has(item)) {
        return false;
      }
    }
    return true;
  },

  /**
   * Return a new set with `item` toggled — removed if present, added if not.
   */
  toggle<T>(set: Set<T>, item: T): Set<T> {
    const result = new Set(set);
    if (result.has(item)) {
      result.delete(item);
    } else {
      result.add(item);
    }
    return result;
  },
};
