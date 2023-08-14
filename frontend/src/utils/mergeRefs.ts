/* Copyright 2023 Marimo. All rights reserved. */
export function mergeRefs<T>(...refs: Array<React.Ref<T>>): React.Ref<T> {
  return (value) => {
    refs.forEach((ref) => {
      if (typeof ref === "function") {
        ref(value);
      } else if (ref != null) {
        (ref as React.MutableRefObject<T | null>).current = value;
      }
    });
  };
}
