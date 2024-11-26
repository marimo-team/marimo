/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { Logger } from "./Logger";

type NoInfer<T> = [T][T extends any ? 0 : never];

export const Maps = {
  /**
   * keyBy for Map, with duplicate key detection.
   */
  keyBy<V, K = string>(
    items: Iterable<V>,
    key: (item: NoInfer<V>) => K,
  ): Map<K, V> {
    const map = new Map<K, V>();
    const duplicateIds = new Set<K>();

    for (const item of items) {
      const k = key(item);
      if (map.has(k)) {
        duplicateIds.add(k);
      }
      map.set(k, item);
    }

    if (duplicateIds.size > 0) {
      Logger.trace(`Duplicate keys: ${[...duplicateIds].join(", ")}`);
    }

    return map;
  },
  collect<T, V, K = string>(
    items: Iterable<T>,
    key: (item: NoInfer<T>) => K,
    mapper: (item: NoInfer<T>) => V,
  ): Map<K, V> {
    return Maps.mapValues(Maps.keyBy(items, key), mapper);
  },
  /**
   * Filter a map by a predicate.
   */
  filterMap<K, V>(
    map: Map<K, V>,
    predicate: (value: V, key: K) => boolean,
  ): Map<K, V> {
    const result = new Map<K, V>();
    for (const [key, value] of map) {
      if (predicate(value, key)) {
        result.set(key, value);
      }
    }
    return result;
  },
  mapValues<K, V, V2>(
    map: Map<K, V>,
    mapper: (value: V, key: K) => V2,
  ): Map<K, V2> {
    const result = new Map<K, V2>();
    for (const [key, value] of map) {
      result.set(key, mapper(value, key));
    }
    return result;
  },
};
