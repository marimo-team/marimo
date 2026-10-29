/* Copyright 2026 Marimo. All rights reserved. */

import { vi } from "vitest";
import { test } from "./scenario-fixture";

test("waits for a pause in typing before sending the latest edit", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "first");
  await vi.advanceTimersByTimeAsync(300);
  user.changeCode("c3", "latest");
  await vi.advanceTimersByTimeAsync(399);
  expect(notebook.edit).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(notebook.edit).toHaveBeenCalledOnce();
  const request = await host.nextRequest();
  request.process();
  request.deliverResponse();
  host.deliverDocument();
  await expect(user.sync()).resolves.toEqual(host.document().revision);
  expect(host.document().cells.get("c3")?.code).toBe("latest");
});

test.for(["response", "document"] as const)(
  "preserves newer typing when the %s arrives first",
  async (first, { expect, session: { user, host, notebook } }) => {
    user.changeCells({ c3: { code: "sent", config: { hide_code: true } } });
    const flushed = user.sync();
    const finished = vi.fn();
    void flushed.then(finished, () => undefined);
    const request = await host.nextRequest();
    request.process();
    user.changeCode("c3", "still typing");

    const deliver = {
      response: () => request.deliverResponse(),
      document: () => host.deliverDocument(),
    };
    deliver[first]();
    await vi.advanceTimersByTimeAsync(0);
    expect(finished).not.toHaveBeenCalled();
    expect(notebook.edit).toHaveBeenCalledOnce();
    expect(user.cell("c3")?.code).toBe("still typing");

    deliver[first === "response" ? "document" : "response"]();
    await vi.advanceTimersByTimeAsync(0);
    expect(user.cell("c3")?.code).toBe("still typing");
    const next = await host.nextRequest();
    next.process();
    next.deliverResponse();
    host.deliverDocument();
    await expect(flushed).resolves.toEqual(host.document().revision);
    const expected = {
      id: "c3",
      code: "still typing",
      name: "_",
      config: {
        column: null,
        disabled: false,
        hide_code: true,
        expand_output: false,
      },
    };
    expect(user.cell("c3")).toEqual(expected);
    expect(host.document().cells.get("c3")).toMatchObject(expected);
    expect(user.status()).toEqual({ status: "idle" });

    host.changeCell("c3", {
      code: "another writer",
      config: { hide_code: false },
    });
    host.deliverDocument();
    expect(user.cell("c3")?.code).toBe("another writer");
    expect(user.cell("c3")?.config.hide_code).toBe(false);
  },
);

test("uses a newer confirmed document for edits that have not been sent", async ({
  expect,
  session: { user, host },
}) => {
  user.changeCode("c3", "local");
  host.changeCell("c3", { name: "remote name" });
  host.deliverDocument();
  const flushed = user.sync();
  const request = await host.nextRequest();
  request.process();
  request.deliverResponse();
  host.deliverDocument();
  await expect(flushed).resolves.toEqual(host.document().revision);
  expect(host.document().cells.get("c3")).toMatchObject({
    code: "local",
    name: "remote name",
  });
});

test.for(["before reset", "during reset", "after snapshot"] as const)(
  "recovers across reset when the response arrives %s",
  async (arrival, { expect, session: { user, host } }) => {
    user.changeCode("c3", "sent");
    const flushed = user.sync();
    const request = await host.nextRequest();
    request.process();
    user.changeCode("c3", "newer typing");
    if (arrival === "before reset") {
      request.deliverResponse();
      await vi.advanceTimersByTimeAsync(0);
    }
    host.reset();
    if (arrival === "during reset") {
      request.deliverResponse();
      await vi.advanceTimersByTimeAsync(0);
    }
    host.changeCell("c1", { code: "unrelated edit" });
    host.deliverSnapshot();
    if (arrival === "after snapshot") {
      await vi.advanceTimersByTimeAsync(0);
      request.deliverResponse();
    }
    expect(user.cell("c3")?.code).toBe("newer typing");
    const next = await host.nextRequest();
    next.process();
    next.deliverResponse();
    host.deliverDocument();
    await expect(flushed).resolves.toEqual(host.document().revision);
    expect(host.document().cells.get("c3")?.code).toBe("newer typing");
    expect(user.cell("c1")?.code).toBe("unrelated edit");
    expect(user.status()).toEqual({ status: "idle" });

    host.changeCell("c3", { code: "another writer" });
    host.deliverDocument();
    expect(user.cell("c3")?.code).toBe("another writer");
  },
);

test.for(["response", "document"] as const)(
  "does not resurrect a cancelled creation when the %s arrives first",
  async (first, { expect, session: { user, host } }) => {
    user.createCell({ id: "new", code: "new cell" });
    const flushed = user.sync();
    const creation = await host.nextRequest();
    user.deleteCell("new");
    host.changeCell("c1", { code: "unrelated edit" });
    host.deliverDocument();
    creation.process();
    const deliver = {
      response: () => creation.deliverResponse(),
      document: () => host.deliverDocument(),
    };
    deliver[first]();
    await vi.advanceTimersByTimeAsync(0);
    expect(user.cell("new")).toBeUndefined();
    expect(user.order()).toEqual(["c1", "c3", "k7f2"]);
    deliver[first === "response" ? "document" : "response"]();
    const deletion = await host.nextRequest();
    deletion.process();
    deletion.deliverResponse();
    host.deliverDocument();
    await expect(flushed).resolves.toEqual(host.document().revision);
    expect(host.document().cells.has("new")).toBe(false);
    expect(user.cell("new")).toBeUndefined();
  },
);

test("releases an edit undone before sending and follows subsequent host changes", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "temporary");
  user.changeCode("c3", "x = 21");
  expect(user.status()).toEqual({ status: "idle" });
  await expect(user.sync()).resolves.toEqual(host.document().revision);

  host.changeCell("c3", { code: "another writer" });
  host.deliverDocument();
  expect(user.cell("c3")?.code).toBe("another writer");
  await vi.advanceTimersByTimeAsync(1000);
  expect(notebook.edit).not.toHaveBeenCalled();
});

test("flushes edits made while an earlier flush is finishing", async ({
  expect,
  session: { user, host, notebook },
}) => {
  const original = host.document().revision;
  const first = user.sync();
  // Let the first flush drain without awaiting its returned promise.
  await Promise.resolve();
  user.changeCode("c3", "new code");
  const second = user.sync();
  const settled = vi.fn();
  void second.then(settled, settled);

  await vi.advanceTimersByTimeAsync(0);
  expect(notebook.edit).toHaveBeenCalledOnce();
  expect(settled).not.toHaveBeenCalled();
  const request = await host.nextRequest();
  request.process();
  expect(host.document().cells.get("c3")?.code).toBe("new code");
  request.deliverResponse();
  host.deliverDocument();
  await expect(second).resolves.toEqual(host.document().revision);
  await expect(first).resolves.toEqual(original);
});
