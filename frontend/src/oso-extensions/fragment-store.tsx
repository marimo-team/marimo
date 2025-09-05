import { compressToEncodedURIComponent, decompressFromEncodedURIComponent } from "lz-string";
import React, { createContext, useContext, useMemo } from "react";

// Implements storing things in the fragment identifier
export class FragmentStore {
    private params: URLSearchParams;

    public static load() {
        return new FragmentStore(new URLSearchParams(window.location.hash.slice(1)));
    }

    constructor(searchParams: URLSearchParams) {
        this.params = searchParams;
    }

    getBoolean(key: string, defaultValue: boolean = false): boolean {
        const value = this.params.get(key);
        if (value === null) return defaultValue;
        return value === "true";
    }

    getString(key: string, defaultValue: string): string;
    getString(key: string, defaultValue?: null): string | null;
    getString(key: string, defaultValue: string | null = null): string | null {
        const value = this.params.get(key);
        if (!value) return defaultValue;
        return (value);
    }

    getCompressedString(key: string, defaultValue: string): string;
    getCompressedString(key: string, defaultValue?: null): string | null;
    getCompressedString(key: string, defaultValue: string | null = null): string | null {
        const value = this.params.get(key);
        if (!value) return defaultValue;
        return decompressFromEncodedURIComponent(value);
    }

    getJSON<T>(key: string, defaultValue: T): T;
    getJSON<T>(key: string, defaultValue?: null): T | null;
    getJSON<T>(key: string, defaultValue: T | null = null): T | null {
      const value = this.getCompressedString(key);
      if (!value) {
        return defaultValue;
      }
      try {
        return JSON.parse(value) as T;
      } catch {
        return null;
      }
    }

    setString(key: string, value: string): void {
        this.params.set(key, value);
    }

    setCompressedString(key: string, value: string): void {
        this.params.set(key, compressToEncodedURIComponent(value));
    }

    setJSON<T>(key: string, value: T): void {
        this.setCompressedString(key, JSON.stringify(value));
    }

    delete(key: string): void {
        this.params.delete(key);
    }

    commit(): void {
        const hash = this.params.toString();
        window.location.hash = hash;
    }
}

const FragmentStoreContext = createContext<FragmentStore | undefined>(undefined);

/**
 * FragmentStoreProvider
 *
 * Provides a FragmentStore instance to descendants.
 * All interaction with the fragment identifier should be done via the store.
 *
 * Usage:
 *   <FragmentStoreProvider>
 *     <YourComponent />
 *   </FragmentStoreProvider>
 *
 * In a component:
 *   const { store } = useFragmentStore();
 *   store.setString("key", "value");
 *   store.commit();
 */
export const FragmentStoreProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  // Create a FragmentStore instance for the current fragment
  const store = useMemo(() => FragmentStore.load(), []);

  return (
    <FragmentStoreContext.Provider value={store}>
      {children}
    </FragmentStoreContext.Provider>
  );
};

/**
 * useFragmentStore
 *
 * Access the FragmentStore context.
 * Throws if used outside a FragmentStoreProvider.
 */
export function useFragmentStore(): FragmentStore {
  const ctx = useContext(FragmentStoreContext);
  if (!ctx) {
    throw new Error("useFragmentStore must be used within a FragmentStoreProvider");
  }
  return ctx;
}