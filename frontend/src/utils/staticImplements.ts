/* Copyright 2024 Marimo. All rights reserved. */
export function staticImplements<T>() {
  return <U extends T>(_constructor: U) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    _constructor;
  };
}
