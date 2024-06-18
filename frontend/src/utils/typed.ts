/* Copyright 2024 Marimo. All rights reserved. */

/**
 * A typed number.
 * This is a compile-time type only and does not exist at runtime.
 * It is used to distinguish between different types of numbers.
 */
export type TypedNumber<T> = number & { __type__: T };

/**
 * A typed string.
 * This is a compile-time type only and does not exist at runtime.
 * It is used to distinguish between different types of strings.
 */
export type TypedString<T> = string & { __type__: T };

export type Identified<T> = { id: string } & T;
