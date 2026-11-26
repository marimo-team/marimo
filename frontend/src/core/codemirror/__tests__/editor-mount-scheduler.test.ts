/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { createEditorMountScheduler } from "../editor-mount-scheduler";

function setup() {
  let pending: (() => void) | null = null;
  const flush = () => {
    const task = pending;
    pending = null;
    task?.();
  };
  const scheduler = createEditorMountScheduler((task) => {
    pending = task;
  });
  const built: string[] = [];
  const register = (cellId: string) =>
    scheduler.register(cellId, () => built.push(cellId));
  return { scheduler, register, built, flush, hasPending: () => !!pending };
}

describe("createEditorMountScheduler", () => {
  it("keeps registrations dormant until prioritized or promoted", () => {
    const { scheduler, register, built, flush, hasPending } = setup();
    register("a");
    register("b");
    register("c");
    expect(hasPending()).toBe(false);

    scheduler.prioritize("b");
    flush();
    expect(built).toEqual(["b"]);
    expect(hasPending()).toBe(false);

    scheduler.promote("c");
    scheduler.promote("c");
    expect(built).toEqual(["b", "c"]);
  });

  it("builds prioritized cells one per task, in prioritization order", () => {
    const { scheduler, register, built, flush, hasPending } = setup();
    register("a");
    register("b");
    register("c");
    scheduler.prioritize("c");
    scheduler.prioritize("a");
    flush();
    expect(built).toEqual(["c"]);
    expect(hasPending()).toBe(true);
    flush();
    expect(built).toEqual(["c", "a"]);
    expect(hasPending()).toBe(false);
  });

  it("does not build a cell that was deprioritized or disposed", () => {
    const { scheduler, register, built, flush } = setup();
    register("a");
    const disposeB = register("b");
    scheduler.prioritize("a");
    scheduler.deprioritize("a");
    scheduler.prioritize("b");
    disposeB();
    flush();
    scheduler.promote("b");
    expect(built).toEqual([]);

    scheduler.prioritize("a");
    flush();
    expect(built).toEqual(["a"]);
  });

  it("ignores prioritize for a cell that is not registered", () => {
    const { scheduler, hasPending } = setup();
    scheduler.prioritize("missing");
    expect(hasPending()).toBe(false);
  });

  it("lets a stale or repeated disposal leave a replacement registration alone", () => {
    const { scheduler, built, flush } = setup();
    const stale = scheduler.register("a", () => built.push("stale"));
    const current = scheduler.register("a", () => built.push("current"));
    stale();
    stale();
    scheduler.prioritize("a");
    flush();
    current();
    expect(built).toEqual(["current"]);
  });

  it("allows a build to register new work for the same cell", () => {
    const { scheduler, built, flush } = setup();
    scheduler.register("a", () => {
      built.push("first");
      scheduler.register("a", () => built.push("second"));
    });
    scheduler.promote("a");
    scheduler.promote("a");
    flush();
    expect(built).toEqual(["first", "second"]);
  });

  it("keeps draining prioritized cells after a build throws", () => {
    const { scheduler, register, built, flush } = setup();
    scheduler.register("a", () => {
      throw new Error("boom");
    });
    register("b");
    scheduler.prioritize("a");
    scheduler.prioritize("b");
    expect(() => flush()).toThrow("boom");
    flush();
    expect(built).toEqual(["b"]);
  });
});
