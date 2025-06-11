/* Copyright 2024 Marimo. All rights reserved. */
/**
 * Make an assertion.
 *
 * If the expression is falsy, an error is thrown with the provided message.
 *
 * @example
 * ```ts
 * const value: boolean = Math.random() <= 0.5;
 * invariant(value, "Value is greater than 0.5");
 * value; // true
 * ```
 *
 * @example
 * ```ts
 * const user: { name?: string } = await fetchUser();
 * invariant(user.name, "User missing name");
 * user.name; // string
 * ```
 *
 * @param expression - The condition to check.
 * @param msg - The error message to throw if the assertion fails.
 * @throws {Error} If `expression` is falsy.
 */
export function invariant(
  expression: unknown,
  msg: string,
): asserts expression {
  if (!expression) {
    throw new Error(msg);
  }
}
