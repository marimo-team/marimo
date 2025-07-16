/* Copyright 2024 Marimo. All rights reserved. */
export const Sets = {
  /**
   * Merge multiple iterables into a single set.
   */
  merge<T>(...sets: Array<Iterable<T>>): Set<T> {
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
   * Immutable delete.
   *
   * If the item is not in the set, return the set unchanged.
   */
  delete<T>(set: Set<T>, item: T): Set<T> {
    if (!set.has(item)) {
      return set;
    }
    const result = new Set(set);
    result.delete(item);
    return result;
  },
};
