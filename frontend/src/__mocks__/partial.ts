/* Copyright 2026 Marimo. All rights reserved. */

/**
 * A partial mock of `T` that throws when a member the test did not provide
 * is read, so a test cannot silently depend on an undefined field.
 */
export function partial<T extends object>(
  members: Partial<T>,
  name = "mock",
): T {
  return new Proxy(members as T, {
    get(target, key, receiver) {
      // Only the members the test gave count as provided, not those every
      // object inherits. Promise detection and well-known symbols may probe
      // any object.
      if (
        Object.hasOwn(target, key) ||
        typeof key === "symbol" ||
        key === "then"
      ) {
        return Reflect.get(target, key, receiver);
      }
      throw new Error(`${name}.${String(key)} is not implemented in this test`);
    },
  });
}
