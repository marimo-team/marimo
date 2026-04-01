/* Copyright 2026 Marimo. All rights reserved. */

/**
 * A typed number.
 * This is a compile-time type only and does not exist at runtime.
 * It is used to distinguish between different types of numbers.
 */
export type TypedNumber<T> = number & { __brand: T };

/**
 * A typed string.
 * This is a compile-time type only and does not exist at runtime.
 * It is used to distinguish between different types of strings.
 */
export type TypedString<T> = string & { __brand: T };

export type Identified<T> = { id: string } & T;
