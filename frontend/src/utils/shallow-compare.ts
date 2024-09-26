/* Copyright 2024 Marimo. All rights reserved. */
import { arrayShallowEquals } from "./arrays";
import { Objects } from "./objects";

export function shallowCompare<T>(a: T, b: T): boolean {
  if (a === b) {
    return true;
  }

  if (a == null || b == null) {
    return false;
  }

  if (Array.isArray(a) && Array.isArray(b)) {
    return arrayShallowEquals(a, b);
  }

  if (typeof a === "object" && typeof b === "object") {
    return shallowCompareObjects(a, b);
  }

  return false;
}

function shallowCompareObjects<T extends object>(a: T, b: T): boolean {
  return (
    Object.keys(a).length === Object.keys(b).length &&
    Objects.keys(a).every((key) => a[key] === b[key])
  );
}
