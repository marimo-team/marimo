/* Copyright 2024 Marimo. All rights reserved. */

import {
  createJSONStorage,
  type SyncStorage,
} from "jotai/vanilla/utils/atomWithStorage";
import { Logger } from "../Logger";
import { availableStorage } from "./storage";

/**
 * Converts a value to and from a serializable format for storage.
 * Useful for data structures that are not natively supported by localStorage (e.g., Maps)
 *
 * @param opts - The options for the storage adapter.
 * @returns - The storage adapter.
 */

export function adaptForLocalStorage<Value, Serializable>(opts: {
  toSerializable: (v: Value) => Serializable;
  fromSerializable: (s: Serializable) => Value;
  storage?: Storage;
}): SyncStorage<Value> {
  const storage = opts.storage || availableStorage;

  return {
    getItem(key, initialValue) {
      try {
        const value = storage.getItem(key);
        if (!value) {
          return initialValue;
        }
        const parsed = JSON.parse(value) as Serializable;
        return opts.fromSerializable(parsed);
      } catch (error) {
        Logger.warn(`Error getting ${key} from storage`, error);
        return initialValue;
      }
    },
    setItem: (key, value): void => {
      storage.setItem(key, JSON.stringify(opts.toSerializable(value)));
    },
    removeItem: (key: string): void => {
      storage.removeItem(key);
    },
  };
}

/**
 * A JSON storage adapter that uses the best available storage.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const jotaiJsonStorage = createJSONStorage<any>(() => availableStorage);
