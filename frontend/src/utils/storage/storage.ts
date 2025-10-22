/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "../Logger";

/**
 * In-memory storage implementation of the Storage interface.
 */
class InMemoryStorage implements Storage {
  private store: Map<string, string> = new Map();

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
    const keys = Array.from(this.store.keys());
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
 * Tests if a specific storage type is available and working
 */
function isStorageAvailable(type: "localStorage" | "sessionStorage"): boolean {
  try {
    const storage: Storage = window[type];
    const testKey = "__storage_test__";
    const testValue = "test";

    // Check if storage exists
    if (!storage) {
      return false;
    }

    // Try to use the storage
    storage.setItem(testKey, testValue);
    const retrieved = storage.getItem(testKey);
    storage.removeItem(testKey);

    return retrieved === testValue;
  } catch (error) {
    // Storage might be disabled or full
    return false;
  }
}

/**
 * Gets the best available storage. Should only be called once.
 */
function getAvailableStorage(): Storage {
  if (isStorageAvailable("localStorage")) {
    return window.localStorage;
  }

  Logger.warn("localStorage is not available, using sessionStorage");

  if (isStorageAvailable("sessionStorage")) {
    return window.sessionStorage;
  }

  Logger.warn("sessionStorage is not available, using in-memory storage");

  return new InMemoryStorage();
}

/**
 * The best available storage. Either localStorage, sessionStorage, or in-memory storage.
 */
export const availableStorage: Storage = getAvailableStorage();
