/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
declare module "*.svg" {
  const content: string | undefined;
  export default content;
}

// Stricter lib types
interface Body {
  json<T = unknown>(): Promise<T>;
}

// Stricter lib types
interface JSON {
  parse(
    text: string,
    reviver?: (this: any, key: string, value: any) => any,
  ): unknown;
}

// Improve type inference for Array.filter with BooleanConstructor
interface Array<T> {
  filter(predicate: BooleanConstructor): Array<NonNullable<T>>;
}
