import { describe, expect, it } from "vitest";
import { createEditorMountScheduler } from "../editor-mount-scheduler";

function makeManualSchedule() {
  let pending: (() => void) | null = null;
  const schedule = (cb: () => void) => {
    pending = cb;
  };
  const flush = () => {
    const cb = pending;
    pending = null;
    cb?.();
  };
  return { schedule, flush, hasPending: () => pending !== null };
}

describe("createEditorMountScheduler", () => {
  it("builds one queued editor per tick in FIFO order, rescheduling between", () => {
    const { schedule, flush, hasPending } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    flush();
    expect(built).toEqual(["a"]);
    expect(hasPending()).toBe(true);
    flush();
    expect(built).toEqual(["a", "b"]);
  });

  it("stops rescheduling once the queue is empty", () => {
    const { schedule, flush, hasPending } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    flush();
    expect(built).toEqual(["a"]);
    expect(hasPending()).toBe(false);
  });

  it("promote builds immediately and removes from the queue", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    s.promote("b");
    expect(built).toEqual(["b"]);
    flush();
    expect(built).toEqual(["b", "a"]);
  });

  it("cancel prevents a queued build", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.cancel("a");
    flush();
    expect(built).toEqual([]);
  });
});
