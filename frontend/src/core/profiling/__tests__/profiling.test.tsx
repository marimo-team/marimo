/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { useProfiling } from "../useProfiling";
import { store } from "@/core/state/jotai";
import {
  componentRenderCountAtom,
  profilingEnabledAtom,
  resetProfilingAtom,
} from "../atoms";
import { render } from "@testing-library/react";

const Probe = ({ name }: { name: string }) => {
  useProfiling(name);
  return null;
};

describe("useProfiling", () => {
  test("disabled path performs zero writes", () => {
    store.set(profilingEnabledAtom, false);
    store.set(componentRenderCountAtom, {});

    let writeFires = 0;
    const unsub = store.sub(componentRenderCountAtom, () => writeFires++);

    const { rerender } = render(<Probe name="Probe" />);
    rerender(<Probe name="Probe" />);
    rerender(<Probe name="Probe" />);
    unsub();

    expect(writeFires).toBe(0);
    expect(store.get(componentRenderCountAtom)).toEqual({});
  });

  test("counts renders when enabled", () => {
    store.set(profilingEnabledAtom, true);
    store.set(componentRenderCountAtom, {});
    const { rerender } = render(<Probe name="Probe" />);
    rerender(<Probe name="Probe" />);
    rerender(<Probe name="Probe" />);

    expect(store.get(componentRenderCountAtom)).toEqual({ Probe: 3 });
  });

  test("resetProfilingAtom clears counters", () => {
    store.set(profilingEnabledAtom, true);
    store.set(componentRenderCountAtom, { Cell: 5 });

    store.set(resetProfilingAtom);
    expect(store.get(componentRenderCountAtom)).toEqual({});
  });
});
