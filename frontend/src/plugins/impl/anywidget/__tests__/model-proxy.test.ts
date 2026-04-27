/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { Model } from "../model";
import { modelProxy } from "../model-proxy";
import type { ModelState } from "../types";

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

describe("Model.on signal option", () => {
  it("removes the listener when the signal aborts", () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const controller = new AbortController();
    const cb = vi.fn();

    model.on("change:count", cb, { signal: controller.signal });
    model.set("count", 1);
    expect(cb).toHaveBeenCalledTimes(1);

    controller.abort();
    model.set("count", 2);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("does not register if the signal is already aborted", () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const controller = new AbortController();
    controller.abort();
    const cb = vi.fn();

    model.on("change:count", cb, { signal: controller.signal });
    model.set("count", 1);
    expect(cb).not.toHaveBeenCalled();
  });

  it("scopes listeners independently per signal", () => {
    const model = new Model<ModelState>({ value: 0 }, createMockComm());
    const view1 = new AbortController();
    const view2 = new AbortController();
    const cb1 = vi.fn();
    const cb2 = vi.fn();

    model.on("change:value", cb1, { signal: view1.signal });
    model.on("change:value", cb2, { signal: view2.signal });

    model.set("value", 1);
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(1);

    view1.abort();
    model.set("value", 2);
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(2);
  });

  it("allows a listener to call off() during emit without skipping siblings", () => {
    // Snapshot-before-iterate guard: a listener that removes itself
    // (typical signal-abort cleanup path) shouldn't drop a sibling.
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const sibling = vi.fn();
    const selfRemoving = vi.fn(() => model.off("change:count", selfRemoving));

    model.on("change:count", selfRemoving);
    model.on("change:count", sibling);

    model.set("count", 1);
    expect(selfRemoving).toHaveBeenCalledTimes(1);
    expect(sibling).toHaveBeenCalledTimes(1);
  });
});

describe("modelProxy", () => {
  it("auto-ties on() to the supplied signal", () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const controller = new AbortController();
    const proxy = modelProxy(model, controller.signal);
    const cb = vi.fn();

    proxy.on("change:count", cb);
    model.set("count", 1);
    expect(cb).toHaveBeenCalledTimes(1);

    // Aborting the signal should clear the listener even though the
    // widget author never wired it up themselves.
    controller.abort();
    model.set("count", 2);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("scopes child listeners to per-view signals", () => {
    const model = new Model<ModelState>({ value: 0 }, createMockComm());
    const view1 = new AbortController();
    const view2 = new AbortController();
    const cb1 = vi.fn();
    const cb2 = vi.fn();

    modelProxy(model, view1.signal).on("change:value", cb1);
    modelProxy(model, view2.signal).on("change:value", cb2);

    model.set("value", 1);
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(1);

    // Dispose view1 — view2's listener stays.
    view1.abort();
    model.set("value", 2);
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(2);
  });

  it("forwards get / set / save_changes", () => {
    const comm = createMockComm();
    const model = new Model<ModelState>({ count: 0 }, comm);
    const controller = new AbortController();
    const proxy = modelProxy(model, controller.signal);

    proxy.set("count", 5);
    expect(proxy.get("count")).toBe(5);
    proxy.save_changes();
    expect(comm.sendUpdate).toHaveBeenCalledWith({ count: 5 });
  });

  it("forwards off() through to the underlying model", () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const controller = new AbortController();
    const proxy = modelProxy(model, controller.signal);
    const cb = vi.fn();

    proxy.on("change:count", cb);
    proxy.off("change:count", cb);
    model.set("count", 1);
    expect(cb).not.toHaveBeenCalled();
  });
});
