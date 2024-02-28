/* Copyright 2024 Marimo. All rights reserved. */
export const Objects = {
  EMPTY: Object.freeze({}) as Record<string, never>,

  mapValues<T, U, K extends string | number>(
    obj: Record<K, T>,
    mapper: (value: T, key: K) => U,
  ): Record<K, U> {
    if (!obj) {
      return obj as Record<K, U>;
    }

    return Objects.fromEntries(
      Objects.entries(obj).map(([key, value]) => [key, mapper(value, key)]),
    );
  },
  /**
   * Type-safe Object.fromEntries
   */
  fromEntries<K extends string | number, V>(obj: Array<[K, V]>): Record<K, V> {
    return Object.fromEntries(obj) as Record<K, V>;
  },
  /**
   * Type-safe Object.entries
   */
  entries<K extends string | number, V>(obj: Record<K, V>): Array<[K, V]> {
    return Object.entries(obj) as Array<[K, V]>;
  },
  /**
   * Type-safe Object.keys
   */
  keys<K extends string | number>(obj: Record<K, unknown>): K[] {
    return Object.keys(obj) as K[];
  },
  /**
   * Type-safe keyBy
   */
  keyBy<T, K extends string | number>(
    items: T[],
    toKey: (item: T) => K | undefined,
  ): Record<K, T> {
    const result: Record<K, T> = {} as Record<K, T>;
    for (const item of items) {
      const key = toKey(item);
      if (key === undefined) {
        continue;
      }
      result[key] = item;
    }
    return result;
  },
  /**
   * Type-safe groupBy
   */
  groupBy<T, K extends string | number, V>(
    items: T[],
    toKey: (item: T) => K | undefined,
    toValue: (item: T) => V,
  ): Record<K, V[]> {
    const result: Record<K, V[]> = {} as Record<K, V[]>;
    for (const item of items) {
      const key = toKey(item);
      if (key === undefined) {
        continue;
      }
      const value = toValue(item);
      if (key in result) {
        result[key].push(value);
      } else {
        result[key] = [value];
      }
    }
    return result;
  },
  filter<K extends string | number, V>(
    obj: Record<K, V>,
    predicate: (value: V, key: K) => boolean,
  ): Record<K, V> {
    const result: Record<K, V> = {} as Record<K, V>;
    for (const [key, value] of Objects.entries(obj)) {
      if (predicate(value, key)) {
        result[key] = obj[key];
      }
    }
    return result;
  },
};
