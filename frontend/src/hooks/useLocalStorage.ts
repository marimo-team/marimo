/* Copyright 2024 Marimo. All rights reserved. */
import { TypedLocalStorage } from "@/utils/localStorage";
import { useState } from "react";

/**
 * React hook to use localStorage
 */
export function useLocalStorage<T>(key: string, defaultValue: T) {
  const storage = new TypedLocalStorage(key, defaultValue);

  const [storedValue, setStoredValue] = useState<T>(() => {
    return storage.get();
  });

  const setValue = (value: T) => {
    setStoredValue(value);
    storage.set(value);
  };

  return [storedValue, setValue] as const;
}
