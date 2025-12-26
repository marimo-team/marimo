/* Copyright 2026 Marimo. All rights reserved. */

import { LRUCache } from "@/utils/lru";
import type {
  DeferredRequestRegistry,
  RequestId,
} from "./DeferredRequestRegistry";

type ToKey<REQ> = (request: REQ) => string;

interface CachingOptions<REQ> {
  toKey?: ToKey<REQ>;
  maxSize?: number;
}

/**
 * Light wrapper adding memoization and in-flight de-duplication on top of
 * DeferredRequestRegistry, keyed by a string representation of the request.
 */
export class CachingRequestRegistry<REQ, RES> {
  private delegate: DeferredRequestRegistry<REQ, RES>;
  private toKey: ToKey<REQ>;
  private cache: LRUCache<string, Promise<RES>>;

  static jsonStringifySortKeys<T>(): ToKey<T> {
    return (o: T) => {
      if (typeof o !== "object" || o === null) {
        return String(o);
      }
      return JSON.stringify(o, Object.keys(o).sort(), 2);
    };
  }

  constructor(
    delegate: DeferredRequestRegistry<REQ, RES>,
    options: CachingOptions<REQ> = {},
  ) {
    this.delegate = delegate;
    this.toKey =
      options.toKey ?? CachingRequestRegistry.jsonStringifySortKeys();
    const maxSize = options.maxSize ?? 128;
    this.cache = new LRUCache<string, Promise<RES>>(maxSize);
  }

  /**
   * Resolve via cache if present, else delegate; de-duplicates concurrent
   * requests with the same key and stores successful results in the cache.
   */
  public request(req: REQ): Promise<RES> {
    const key = this.toKey(req);

    const cached = this.cache.get(key);
    if (cached !== undefined) {
      return cached;
    }

    const promise = this.delegate.request(req);
    this.cache.set(key, promise);
    return promise.catch((error) => {
      this.cache.delete(key);
      throw error;
    });
  }

  // Path through to the delegate
  public resolve(requestId: RequestId, response: RES) {
    this.delegate.resolve(requestId, response);
  }

  // Path through to the delegate
  public reject(requestId: RequestId, error: Error) {
    this.delegate.reject(requestId, error);
  }
}
