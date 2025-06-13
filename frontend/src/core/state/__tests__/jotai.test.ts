/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { describe, expect, it } from "vitest";
import { store, waitFor } from "../jotai";

describe("waitFor function", () => {
  it("should resolve when the atom satisfies the predicate", async () => {
    const testAtom = atom(0);
    store.set(testAtom, 10);

    const result = await waitFor(testAtom, (value) => value === 10);
    expect(result).toBe(10);
  });

  it("should resolve when the atom changes to satisfy the predicate", async () => {
    const testAtom = atom(0);

    setTimeout(() => store.set(testAtom, 15), 5);
    setTimeout(() => store.set(testAtom, 20), 10);

    const result = await waitFor(testAtom, (value) => value === 20);
    expect(result).toBe(20);
  });
});
