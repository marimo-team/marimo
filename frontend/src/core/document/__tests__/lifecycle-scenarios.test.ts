/* Copyright 2026 Marimo. All rights reserved. */

import { vi } from "vitest";
import { test } from "./scenario-fixture";

test("closing a session before the debounce prevents submission", async ({
  expect,
  session: { user, notebook, controller },
}) => {
  user.changeCode("c3", "local");
  const reason = new Error("Editing session ended");
  controller.abort(reason);
  await vi.advanceTimersByTimeAsync(1000);
  expect(notebook.edit).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
  await expect(user.sync()).rejects.toBe(reason);
});

test("closing a session before a queued flush starts prevents submission", async ({
  expect,
  session: { user, notebook, controller },
}) => {
  user.changeCode("c3", "local");
  const flushed = user.sync();
  const reason = new Error("Editing session ended");
  controller.abort(reason);
  await expect(flushed).rejects.toBe(reason);
  expect(notebook.edit).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});

test.for(["request", "confirmation", "retry"] as const)(
  "closing a session during %s stops synchronization",
  async (phase, { expect, session: { user, host, notebook, controller } }) => {
    user.changeCode("c3", "local");
    const flushed = user.sync();
    const request = await host.nextRequest();
    if (phase === "confirmation") {
      request.process();
      request.deliverResponse();
    } else if (phase === "retry") {
      request.loseResponse();
    }
    await vi.advanceTimersByTimeAsync(0);
    const reason = new Error("Editing session ended");
    controller.abort(reason);
    await expect(flushed).rejects.toBe(reason);
    if (phase === "request") {
      expect(request.signal.aborted).toBe(true);
    }

    host.changeCell("c1", { code: "later" });
    host.deliverSnapshot();
    user.changeCode("c3", "after closing");
    await vi.advanceTimersByTimeAsync(1000);
    expect(notebook.edit).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
    await expect(user.sync()).rejects.toBe(reason);
    await expect(user.retry()).rejects.toBe(reason);
  },
);
