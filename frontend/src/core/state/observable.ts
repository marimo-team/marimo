/* Copyright 2024 Marimo. All rights reserved. */
import type { Atom } from "jotai";
import type { JotaiStore } from "./jotai";

export interface Observable<T> {
  get(): T;
  sub(callback: (value: T) => void): () => void;
}

/**
 * Create an observable from a Jotai atom.
 *
 * This is just a simpler read-only API that hides the Jotai store.
 */
export function createObservable<T>(
  value: Atom<T>,
  store: JotaiStore,
): Observable<T> {
  return {
    get: () => store.get(value),
    sub: (callback) => store.sub(value, () => callback(store.get(value))),
  };
}
