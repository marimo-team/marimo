/* Copyright 2026 Marimo. All rights reserved. */

/**
 * MultiMap: a Map<K, V[]> with convenient helpers.
 */
export class MultiMap<K, V> {
  private map = new Map<K, V[]>();

  public get(key: K): V[] {
    return this.map.get(key) ?? [];
  }

  public set(key: K, values: V[]): void {
    this.map.set(key, values);
  }

  public add(key: K, value: V): void {
    if (this.map.has(key)) {
      // oxlint-disable-next-line typescript/no-non-null-assertion
      this.map.get(key)!.push(value);
    } else {
      this.map.set(key, [value]);
    }
  }

  public has(key: K): boolean {
    return this.map.has(key);
  }

  public delete(key: K): boolean {
    return this.map.delete(key);
  }

  public clear(): void {
    this.map.clear();
  }

  public keys(): IterableIterator<K> {
    return this.map.keys();
  }

  public values(): IterableIterator<V[]> {
    return this.map.values();
  }

  public entries(): IterableIterator<[K, V[]]> {
    return this.map.entries();
  }

  public forEach(
    callback: (values: V[], key: K, map: Map<K, V[]>) => void,
  ): void {
    this.map.forEach(callback);
  }

  /**
   * Flatten all values into a single array.
   */
  public flatValues(): V[] {
    const result: V[] = [];
    for (const arr of this.map.values()) {
      result.push(...arr);
    }
    return result;
  }

  /**
   * Number of keys in the MultiMap.
   */
  public get size(): number {
    return this.map.size;
  }
}
