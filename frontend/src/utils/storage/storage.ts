/* Copyright 2024 Marimo. All rights reserved. */

import { getIframeCapabilities } from "../capabilities";

/**
 * In-memory storage implementation of the Storage interface.
 */
class InMemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) || null;
  }

  key(index: number): string | null {
    const keys = [...this.store.keys()];
    return keys[index] || null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

/**
 * Gets the best available storage. Should only be called once.
 */
function getAvailableStorage(): Storage {
  const { hasLocalStorage, hasSessionStorage } = getIframeCapabilities();

  if (hasLocalStorage) {
    return window.localStorage;
  }

  if (hasSessionStorage) {
    return window.sessionStorage;
  }

  return new InMemoryStorage();
}

/**
 * The best available storage. Either localStorage, sessionStorage, or in-memory storage.
 */
export const availableStorage: Storage = getAvailableStorage();
