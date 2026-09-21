/* Copyright 2026 Marimo. All rights reserved. */
import { isPlainObject } from "lodash-es";

export const PAGE_SIZE = 30;

interface Page {
  path: string;
  remaining: number;
}

interface Options {
  limits: Record<string, number>;
  pageSize: number;
}

export function paginateJson(data: object, { limits, pageSize }: Options) {
  const originals = new WeakMap<object, object>();
  const pages = new Map<symbol, Page>();

  function visit(node: object, path: string[]): object {
    if (!Array.isArray(node) && !isPlainObject(node)) {
      return node;
    }
    const pathKey = JSON.stringify(path);
    const limit = limits[pathKey] ?? pageSize;
    const keys = Array.isArray(node)
      ? Array.from({ length: Math.min(node.length, limit) }, (_, i) =>
          String(i),
        )
      : Object.keys(node).slice(0, limit);
    const count = Array.isArray(node) ? node.length : Object.keys(node).length;
    const result: object = Array.isArray(node) ? [] : Object.create(null);
    originals.set(result, node);

    for (const key of keys) {
      // Materialize only the branches the viewer reads, including after expansion.
      Object.defineProperty(result, key, {
        enumerable: true,
        configurable: true,
        get() {
          const original: unknown = Reflect.get(node, key);
          const value =
            original !== null && typeof original === "object"
              ? visit(original, [...path, key])
              : original;
          Object.defineProperty(result, key, {
            value,
            enumerable: true,
            configurable: true,
          });
          return value;
        },
      });
    }
    if (count > limit) {
      const marker = Symbol("show more");
      pages.set(marker, { remaining: count - limit, path: pathKey });
      let key = Array.isArray(node) ? String(limit) : "";
      while (Object.hasOwn(result, key)) {
        key += "\0";
      }
      Object.defineProperty(result, key, { value: marker, enumerable: true });
    }
    return result;
  }

  return {
    data: visit(data, []),
    getOriginal(value: unknown): unknown {
      return value !== null && typeof value === "object"
        ? (originals.get(value) ?? value)
        : value;
    },
    getPage(value: unknown): Page | undefined {
      return typeof value === "symbol" ? pages.get(value) : undefined;
    },
  };
}

export function estimateExpandedLines(
  node: unknown,
  cap: number,
  depth = 0,
): number {
  if (
    depth > 4 ||
    node === null ||
    node === undefined ||
    typeof node !== "object"
  ) {
    return 1;
  }
  const children: unknown[] = Array.isArray(node) ? node : Object.values(node);
  let lines = 0;
  for (let i = 0; i < children.length && lines < cap; i++) {
    const child = children[i];
    if (child === null || child === undefined || typeof child !== "object") {
      lines++;
    } else {
      const childLen = Array.isArray(child)
        ? child.length
        : Object.keys(child).length;
      lines +=
        childLen <= 8
          ? estimateExpandedLines(child, cap - lines, depth + 1)
          : 1;
    }
  }
  return lines;
}

export function shouldExpandNode(
  _isExpanded: boolean,
  { value, level }: { value?: object; level: number },
): boolean {
  if (level <= 1) {
    return true;
  }
  if (level > 5) {
    return false;
  }
  if (value === null || value === undefined || typeof value !== "object") {
    return true;
  }
  const len = Array.isArray(value) ? value.length : Object.keys(value).length;
  if (len === 0) {
    return true;
  }
  if (len > 200) {
    return false;
  }
  return estimateExpandedLines(value, 150) <= 120;
}

export function determineMaxDisplayLength(data: unknown): number | undefined {
  if (!Array.isArray(data)) {
    return undefined;
  }
  const sample = data.slice(0, 15);
  let maxLength = 0;
  for (const el of sample) {
    if (Array.isArray(el)) {
      for (const next of el.slice(0, 5)) {
        if (Array.isArray(next)) {
          return 5;
        }
      }
      maxLength = Math.max(maxLength, el.length);
    }
  }
  if (maxLength <= 20) {
    return undefined;
  }
  return maxLength >= 50 ? 5 : 10;
}
