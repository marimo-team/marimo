/* Copyright 2024 Marimo. All rights reserved. */

interface TimedCacheOptions {
  /** Time to live for cache entries in milliseconds. */
  ttl: number;
}

export class TimedCache<T> {
  private ttl: number;
  private cache = new Map<string, { data: T; timestamp: number }>();

  constructor(options: TimedCacheOptions) {
    this.ttl = options.ttl;
  }

  private cleanupExpiredEntries(): void {
    const now = Date.now();
    for (const [key, cached] of this.cache.entries()) {
      if (now - cached.timestamp > this.ttl) {
        this.cache.delete(key);
      }
    }
  }

  get(key: string): T | undefined {
    this.cleanupExpiredEntries();

    const cached = this.cache.get(key);
    if (!cached) {
      return undefined;
    }

    const now = Date.now();
    if (now - cached.timestamp > this.ttl) {
      this.cache.delete(key);
      return undefined;
    }

    return cached.data;
  }

  set(key: string, data: T): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
    });
  }

  clear(): void {
    this.cache.clear();
  }
}
