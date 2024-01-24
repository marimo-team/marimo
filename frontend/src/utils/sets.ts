/* Copyright 2024 Marimo. All rights reserved. */
export const Sets = {
  merge<T>(...sets: Array<Set<T>>): Set<T> {
    const result = new Set<T>();
    for (const set of sets) {
      for (const item of set) {
        result.add(item);
      }
    }
    return result;
  },
};
