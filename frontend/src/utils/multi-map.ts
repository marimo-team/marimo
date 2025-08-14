/* Copyright 2024 Marimo. All rights reserved. */

/**
 * MultiMap: a Map<K, V[]> with convenient helpers.
 */
export class MultiMap<K, V> {
  private map = new Map<K, V[]>();

  get(key: K): V[] {
    return this.map.get(key) ?? [];
  }

  set(key: K, values: V[]): void {
    this.map.set(key, values);
  }

  add(key: K, value: V): void {
    if (this.map.has(key)) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      this.map.get(key)!.push(value);
    } else {
      this.map.set(key, [value]);
    }
  }

  has(key: K): boolean {
    return this.map.has(key);
  }

  delete(key: K): boolean {
    return this.map.delete(key);
  }

  clear(): void {
    this.map.clear();
  }

  keys(): IterableIterator<K> {
    return this.map.keys();
  }

  values(): IterableIterator<V[]> {
    return this.map.values();
  }

  entries(): IterableIterator<[K, V[]]> {
    return this.map.entries();
  }

  forEach(callback: (values: V[], key: K, map: Map<K, V[]>) => void): void {
    this.map.forEach(callback);
  }

  /**
   * Flatten all values into a single array.
   */
  flatValues(): V[] {
    const result: V[] = [];
    for (const arr of this.map.values()) {
      result.push(...arr);
    }
    return result;
  }

  /**
   * Number of keys in the MultiMap.
   */
  get size(): number {
    return this.map.size;
  }
}
