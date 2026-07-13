/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import { findCacheSites, findDeclarationSites } from "../analyzer";

function pythonState(code: string) {
  return EditorState.create({ doc: code, extensions: [python()] });
}

function run(names: string[], code: string) {
  return findDeclarationSites({
    state: pythonState(code),
    names: new Set(names),
  });
}

describe("findDeclarationSites", () => {
  it("finds a simple assignment", () => {
    const code = 'df = pd.read_csv("a.csv")';
    const targets = run(["df"], code);
    expect(targets).toEqual([{ from: 0, to: 2, name: "df" }]);
    expect(code.slice(targets[0].from, targets[0].to)).toBe("df");
  });

  it("only matches the given names", () => {
    const targets = run(["df"], "df = 1\nother = 2");
    expect(targets.map((t) => t.name)).toEqual(["df"]);
  });

  it("handles annotated assignments", () => {
    const targets = run(["df", "DataFrame"], "df: DataFrame = load()");
    expect(targets.map((t) => t.name)).toEqual(["df"]);
  });

  it("handles chained assignments", () => {
    const targets = run(["a", "b"], "a = b = load()");
    expect(targets.map((t) => t.name).toSorted()).toEqual(["a", "b"]);
  });

  it("handles tuple and list unpacking", () => {
    expect(run(["x", "y"], "x, y = f()").map((t) => t.name)).toEqual([
      "x",
      "y",
    ]);
    expect(run(["a", "b"], "(a, b) = f()").map((t) => t.name)).toEqual([
      "a",
      "b",
    ]);
    expect(run(["a", "b"], "[a, b] = f()").map((t) => t.name)).toEqual([
      "a",
      "b",
    ]);
  });

  it("handles a parenthesized single target", () => {
    expect(run(["df"], "(df) = load()").map((t) => t.name)).toEqual(["df"]);
  });

  it("returns only the first assignment site per name", () => {
    const targets = run(["df"], "df = 1\ndf = 2");
    expect(targets).toEqual([{ from: 0, to: 2, name: "df" }]);
  });

  it("ignores attribute and subscript targets", () => {
    expect(run(["df"], "obj.df = 1")).toEqual([]);
    expect(run(["df"], "data[df] = 1")).toEqual([]);
  });

  it("ignores augmented assignments", () => {
    expect(run(["df"], "df += 1")).toEqual([]);
  });

  it("ignores assignments in function, lambda, and class scopes", () => {
    expect(run(["df"], "def f():\n    df = 1")).toEqual([]);
    expect(run(["df"], "class A:\n    df = 1")).toEqual([]);
  });

  it("finds assignments in top-level control flow", () => {
    const targets = run(["df"], "if cond:\n    df = load()");
    expect(targets.map((t) => t.name)).toEqual(["df"]);
  });

  it("ignores usages that are not assignments", () => {
    expect(run(["df"], "print(df)")).toEqual([]);
  });

  it("returns nothing for syntax errors", () => {
    expect(run(["df"], "df = (")).toEqual([]);
  });

  it("returns nothing for an empty name set", () => {
    expect(run([], "df = 1")).toEqual([]);
  });
});

describe("findCacheSites", () => {
  function runCache(code: string) {
    return findCacheSites(pythonState(code)).map((site) =>
      code.slice(site.from, site.to),
    );
  }

  it("matches decorator usage", () => {
    expect(runCache("@mo.cache\ndef f():\n    return 1")).toEqual(["mo.cache"]);
  });

  it("extends past decorator arguments", () => {
    expect(
      runCache("@mo.cache(pin_modules=True)\ndef f():\n    return 1"),
    ).toEqual(["mo.cache(pin_modules=True)"]);
  });

  it("extends past call arguments", () => {
    expect(runCache("g = mo.cache(f)")).toEqual(["mo.cache(f)"]);
    expect(runCache("g = mo.cache(f, pin_modules=True)")).toEqual([
      "mo.cache(f, pin_modules=True)",
    ]);
  });

  it("does not extend a bare reference or an enclosing call", () => {
    expect(runCache("g = mo.cache")).toEqual(["mo.cache"]);
    expect(runCache("print(mo.cache, 1)")).toEqual(["mo.cache"]);
  });

  it("matches persistent_cache context manager usage", () => {
    expect(runCache('with mo.persistent_cache("k"):\n    pass')).toEqual([
      'mo.persistent_cache("k")',
    ]);
  });

  it("matches multiple occurrences", () => {
    expect(runCache("mo.cache(f)\nmo.persistent_cache(g)")).toHaveLength(2);
  });

  it("does not match similar names", () => {
    expect(runCache("memo.cache(f)")).toEqual([]);
    expect(runCache("mo.cached(f)")).toEqual([]);
    expect(runCache("mo.cache_info()")).toEqual([]);
  });

  it("does not match attribute chains like obj.mo.cache", () => {
    expect(runCache("obj.mo.cache(f)")).toEqual([]);
    expect(runCache("self.mo.persistent_cache(g)")).toEqual([]);
  });

  it("does not match mentions in comments or strings", () => {
    expect(runCache("# uses mo.cache internally")).toEqual([]);
    expect(runCache('x = "mo.cache"')).toEqual([]);
    expect(runCache("mo.cache(f)  # not mo.persistent_cache")).toEqual([
      "mo.cache(f)",
    ]);
  });

  describe("bound name and cache name extraction", () => {
    function sites(code: string) {
      return findCacheSites(pythonState(code)).map(
        ({ boundName, cacheName }) => ({ boundName, cacheName }),
      );
    }

    it("extracts the decorated function name", () => {
      expect(sites("@mo.cache\ndef add(a, b):\n    return a + b")).toEqual([
        { boundName: "add", cacheName: null },
      ]);
      expect(
        sites("@mo.cache(pin_modules=True)\ndef add(a, b):\n    return a + b"),
      ).toEqual([{ boundName: "add", cacheName: null }]);
    });

    it("extracts the assignment target", () => {
      expect(sites("g = mo.cache(f)")).toEqual([
        { boundName: "g", cacheName: null },
      ]);
    });

    it("extracts the with-statement binding and cache name", () => {
      expect(sites('with mo.persistent_cache("k") as c:\n    pass')).toEqual([
        { boundName: "c", cacheName: "k" },
      ]);
      expect(sites('with mo.persistent_cache("k"):\n    pass')).toEqual([
        { boundName: null, cacheName: "k" },
      ]);
      expect(sites('with mo.persistent_cache(name="k"):\n    pass')).toEqual([
        { boundName: null, cacheName: "k" },
      ]);
    });

    it("extracts nothing for bare expressions", () => {
      expect(sites("mo.cache(f)")).toEqual([
        { boundName: null, cacheName: null },
      ]);
    });
  });
});
