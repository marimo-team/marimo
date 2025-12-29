/* Copyright 2026 Marimo. All rights reserved. */
import type { Observable } from "../observable";

export function createMockObservable<T>(
  initialValue: T,
): Observable<T> & { set: (value: T) => void } {
  let value = initialValue;
  const subscribers = new Set<(value: T) => void>();

  return {
    get: () => value,
    sub: (callback) => {
      subscribers.add(callback);
      return () => {
        subscribers.delete(callback);
      };
    },
    set: (newValue: T) => {
      value = newValue;
      subscribers.forEach((callback) => callback(newValue));
    },
  };
}
