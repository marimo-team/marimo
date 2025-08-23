/* Copyright 2024 Marimo. All rights reserved. */

import type { SyncStorage } from "jotai/vanilla/utils/atomWithStorage";
import { Logger } from "./Logger";

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
}): SyncStorage<Value> {
  return {
    getItem(key, initialValue) {
      try {
        const value = localStorage.getItem(key);
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
      localStorage.setItem(key, JSON.stringify(opts.toSerializable(value)));
    },
    removeItem: (key: string): void => {
      localStorage.removeItem(key);
    },
  };
}
