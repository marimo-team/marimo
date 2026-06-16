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

  it("builds prioritized cells before earlier-queued ones", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    s.request("c", () => built.push("c"));
    s.prioritize("c");
    flush();
    flush();
    flush();
    expect(built).toEqual(["c", "a", "b"]);
  });

  it("builds multiple prioritized cells in prioritization order, then FIFO", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    s.request("c", () => built.push("c"));
    s.request("d", () => built.push("d"));
    s.prioritize("d");
    s.prioritize("b");
    flush();
    flush();
    flush();
    flush();
    expect(built).toEqual(["d", "b", "a", "c"]);
  });

  it("ignores prioritize for a cell that is not queued", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.prioritize("not-queued");
    flush();
    expect(built).toEqual(["a"]);
  });

  it("deprioritize reverts a cell to FIFO order without dropping it", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    s.prioritize("b");
    s.deprioritize("b");
    flush();
    flush();
    expect(built).toEqual(["a", "b"]);
  });

  it("keeps draining the queue after a build throws", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => {
      throw new Error("boom");
    });
    s.request("b", () => built.push("b"));
    expect(() => flush()).toThrow("boom");
    flush();
    expect(built).toEqual(["b"]);
  });

  it("cancel removes a prioritized cell", () => {
    const { schedule, flush } = makeManualSchedule();
    const built: string[] = [];
    const s = createEditorMountScheduler(schedule);
    s.request("a", () => built.push("a"));
    s.request("b", () => built.push("b"));
    s.prioritize("b");
    s.cancel("b");
    flush();
    flush();
    expect(built).toEqual(["a"]);
  });
});
