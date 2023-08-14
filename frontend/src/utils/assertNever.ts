/* Copyright 2023 Marimo. All rights reserved. */
import { Logger } from "./Logger";

/**
 * Type-safe exhaustiveness check for discriminated unions.
 */
export function assertNever(x: never): never {
  throw new Error(`Unexpected object: ${x}`);
}

/**
 * Like assertNever, but logs the unexpected object to the console.
 * Useful for exhaustiveness checks but without throwing an error.
 */
export function logNever(x: never): void {
  Logger.warn(`Unexpected object: ${JSON.stringify(x)}`);
  return x;
}
