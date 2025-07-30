/* Copyright 2024 Marimo. All rights reserved. */
export function mergeRefs<T>(
  ...refs: Array<React.Ref<T>>
): (value: T | null) => void {
  return (value) => {
    refs.forEach((ref) => {
      if (typeof ref === "function") {
        ref(value);
      } else if (ref != null) {
        ref.current = value;
      }
    });
  };
}
