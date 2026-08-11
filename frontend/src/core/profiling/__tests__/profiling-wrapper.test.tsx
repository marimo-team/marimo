/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { store } from "@/core/state/jotai";
import { profilerEventsAtom, profilingEnabledAtom } from "../atoms";
import { ProfilingWrapper } from "../profiling-wrapper";

const Probe = () => <div>probe</div>;

describe("ProfilingWrapper", () => {
  beforeEach(() => {
    store.set(profilingEnabledAtom, false);
    store.set(profilerEventsAtom, []);
  });

  test("records render durations when enabled", () => {
    store.set(profilingEnabledAtom, true);

    const { rerender } = render(
      <ProfilingWrapper name="Probe">
        <Probe />
      </ProfilingWrapper>,
    );
    rerender(
      <ProfilingWrapper name="Probe">
        <Probe />
      </ProfilingWrapper>,
    );

    const events = store.get(profilerEventsAtom);
    expect(events.length).toBeGreaterThanOrEqual(2);
    expect(events.every((e) => e.id === "Probe")).toBe(true);
    expect(events[0].phase).toBe("mount");
    expect(events[1].phase).toBe("update");
    expect(events.every((e) => e.actualDuration >= 0)).toBe(true);
  });

  test("records nothing when disabled", () => {
    const { rerender } = render(
      <ProfilingWrapper name="Probe">
        <Probe />
      </ProfilingWrapper>,
    );
    rerender(
      <ProfilingWrapper name="Probe">
        <Probe />
      </ProfilingWrapper>,
    );

    expect(store.get(profilerEventsAtom)).toEqual([]);
  });
});
