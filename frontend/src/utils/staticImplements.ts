/* Copyright 2026 Marimo. All rights reserved. */
export function staticImplements<T>() {
  return <U extends T>(_constructor: U) => {
    // oxlint-disable-next-line typescript/no-unused-expressions
    _constructor;
  };
}
