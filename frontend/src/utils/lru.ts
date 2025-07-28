/* Copyright 2024 Marimo. All rights reserved. */

interface LRUCacheOptions<K, V> {
  create: (key: K) => V;
}

export class LRUCache<K, V> {
  private maxSize: number;
  private cache = new Map<K, V>();
  private options: LRUCacheOptions<K, V>;

  constructor(maxSize: number, options: LRUCacheOptions<K, V>) {
    this.maxSize = maxSize;
    this.options = options;
  }

  public getOrCreate(key: K): V {
    const item = this.cache.get(key);
    if (item !== undefined) {
      return item;
    }
    const newItem = this.options.create(key);
    this.cache.set(key, newItem);
    return newItem;
  }

  public get(key: K): V | undefined {
    const item = this.cache.get(key);
    if (item !== undefined) {
      // re-insert for LRU effect
      this.cache.delete(key);
      this.cache.set(key, item);
    }
    return item;
  }

  public set(key: K, value: V) {
    // if key already in cache, remove it so we move it to the "fresh" position
    if (this.cache.has(key)) {
      this.cache.delete(key);
    }
    this.cache.set(key, value);

    // evict oldest
    if (this.cache.size > this.maxSize) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }
  }

  public keys() {
    return this.cache.keys();
  }

  public values() {
    return this.cache.values();
  }

  public entries() {
    return this.cache.entries();
  }
}
