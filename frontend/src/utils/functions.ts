/* Copyright 2024 Marimo. All rights reserved. */
export const Functions = {
  NOOP: () => {
    return;
  },
  ASYNC_NOOP: async () => {
    return;
  },
  THROW: () => {
    throw new Error("Should not be called");
  },
  asUpdater: <T>(updater: T | ((value: T) => T)): ((value: T) => T) => {
    return typeof updater === "function"
      ? (updater as (value: T) => T)
      : () => updater;
  },
  identity: <T>(value: T): T => {
    return value;
  },
};

export function throwNotImplemented(): never {
  throw new Error("Not implemented");
}
