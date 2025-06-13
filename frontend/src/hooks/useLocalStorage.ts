/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import { TypedLocalStorage } from "@/utils/localStorage";

/**
 * React hook to use localStorage
 */
export function useLocalStorage<T>(key: string, defaultValue: T) {
  const storage = new TypedLocalStorage(defaultValue);

  const [storedValue, setStoredValue] = useState<T>(() => {
    return storage.get(key);
  });

  const setValue = (value: T) => {
    setStoredValue(value);
    storage.set(key, value);
  };

  return [storedValue, setValue] as const;
}
