/* Copyright 2026 Marimo. All rights reserved. */

import { vi } from "vitest";
import { test } from "./scenario-fixture";

test.for(["response", "document"] as const)(
  "keeps a conflicting batch intact and retries explicitly with %s first",
  async (first, { expect, session: { user, host, notebook } }) => {
    // The first change is valid; the second conflicts. Neither may commit.
    user.changeCells({
      c1: { code: "other local edit" },
      c3: { code: "local" },
    });
    const synced = user.sync();
    const request = await host.nextRequest();
    host.changeCell("c3", { code: "remote", name: "remote name" });
    const remote = host.document();
    expect(user.cell("c3")?.code).toBe("local");
    request.process();
    expect(host.document()).toEqual(remote);
    user.changeCode("c3", "updated local");

    if (first === "document") {
      host.deliverDocument();
    }
    request.deliverResponse();
    await expect(synced).rejects.toThrow("conflict");
    expect(user.status()).toMatchObject({ status: "error", retryable: true });
    if (first === "response") {
      host.deliverDocument();
    }
    await vi.advanceTimersByTimeAsync(2000);
    expect(notebook.edit).toHaveBeenCalledOnce();
    expect(user.cell("c3")?.code).toBe("updated local");
    expect(user.cell("c1")?.code).toBe("other local edit");

    const retried = user.retry();
    const retry = await host.nextRequest();
    expect(retry.idempotencyKey).not.toBe(request.idempotencyKey);
    retry.process();
    retry.deliverResponse();
    host.deliverDocument();
    await expect(retried).resolves.toEqual(host.document().revision);
    expect(host.document().cells.get("c1")?.code).toBe("other local edit");
    expect(host.document().cells.get("c3")).toMatchObject({
      code: "updated local",
      name: "remote name",
    });
    expect(user.cell("c3")).toMatchObject({
      code: "updated local",
      name: "remote name",
    });
    expect(user.status()).toEqual({ status: "idle" });
  },
);

test("waits for the conflicting revision before allowing a retry", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "local");
  const synced = user.sync();
  const request = await host.nextRequest();
  host.changeCell("c3", { code: "remote" });
  request.process();
  request.deliverResponse();
  await expect(synced).rejects.toThrow("conflict");
  await expect(user.retry()).rejects.toThrow("Wait for the host");
  expect(notebook.edit).toHaveBeenCalledOnce();
  expect(user.cell("c3")?.code).toBe("local");

  host.deliverDocument();
  const retried = user.retry();
  const retry = await host.nextRequest();
  retry.process();
  retry.deliverResponse();
  host.deliverDocument();
  await expect(retried).resolves.toEqual(host.document().revision);
  expect(host.document().cells.get("c3")?.code).toBe("local");
  expect(user.status()).toEqual({ status: "idle" });
});

test("replays a lost response without committing twice or losing newer typing", async ({
  expect,
  session: { user, host },
}) => {
  user.changeCode("c3", "sent");
  const flushed = user.sync();
  const request = await host.nextRequest();
  request.process();
  const committed = host.document();
  host.deliverDocument();
  user.changeCode("c3", "newer");
  request.loseResponse();

  await vi.advanceTimersByTimeAsync(500);
  const retry = await host.nextRequest();
  expect(retry.idempotencyKey).toBe(request.idempotencyKey);
  expect(retry.changes).toEqual(request.changes);
  retry.process();
  expect(host.document()).toEqual(committed);
  retry.deliverResponse();

  const next = await host.nextRequest();
  expect(next.idempotencyKey).not.toBe(request.idempotencyKey);
  next.process();
  next.deliverResponse();
  host.deliverDocument();
  await expect(flushed).resolves.toEqual(host.document().revision);
  expect(host.document().revision.version).toBe(committed.revision.version + 1);
  expect(host.document().cells.get("c3")?.code).toBe("newer");
  expect(user.cell("c3")?.code).toBe("newer");
});

test("ignores a timed-out attempt that completes after its retry", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "local");
  const flushed = user.sync();
  const first = await host.nextRequest();
  await vi.advanceTimersByTimeAsync(10_500);
  const retry = await host.nextRequest();
  expect(first.signal.aborted).toBe(true);
  expect(retry.idempotencyKey).toBe(first.idempotencyKey);
  retry.process();
  const committed = host.document();
  retry.deliverResponse();
  host.deliverDocument();
  await expect(flushed).resolves.toEqual(committed.revision);
  first.process();
  first.deliverResponse();
  await vi.advanceTimersByTimeAsync(0);
  expect(host.document()).toEqual(committed);
  expect(user.cell("c3")?.code).toBe("local");
  expect(notebook.edit).toHaveBeenCalledTimes(2);
});

test("a manual retry reuses the committed edit after automatic retries give up", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "sent");
  const synced = user.sync();
  const request = await host.nextRequest();
  request.process();
  const committed = host.document();
  request.loseResponse();
  for (const delay of [500, 1000]) {
    await vi.advanceTimersByTimeAsync(delay);
    const retry = await host.nextRequest();
    retry.process();
    retry.loseResponse();
  }
  await expect(synced).rejects.toThrow("Connection lost");
  expect(user.status()).toMatchObject({ status: "error", retryable: true });
  expect(notebook.edit).toHaveBeenCalledTimes(3);
  expect(host.document()).toEqual(committed);

  const retried = user.retry();
  const retry = await host.nextRequest();
  expect(retry.idempotencyKey).toBe(request.idempotencyKey);
  expect(retry.changes).toEqual(request.changes);
  retry.process();
  retry.deliverResponse();
  host.deliverDocument();
  await expect(retried).resolves.toEqual(committed.revision);
  expect(host.document()).toEqual(committed);
  expect(user.status()).toEqual({ status: "idle" });
  expect(notebook.edit).toHaveBeenCalledTimes(4);
});

test("refuses a manual retry after the safe retry window while retaining the draft", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "sent");
  const synced = user.sync();
  const request = await host.nextRequest();
  request.process();
  const committed = host.document();
  request.loseResponse();
  for (const delay of [500, 1000]) {
    await vi.advanceTimersByTimeAsync(delay);
    const retry = await host.nextRequest();
    retry.process();
    retry.loseResponse();
  }
  await expect(synced).rejects.toThrow("Connection lost");
  expect(user.status()).toMatchObject({ status: "error", retryable: true });

  await vi.advanceTimersByTimeAsync(60_000);
  await expect(user.retry()).rejects.toThrow("retry window expired");
  expect(user.status()).toMatchObject({ status: "error", retryable: false });
  expect(notebook.edit).toHaveBeenCalledTimes(3);
  expect(host.document()).toEqual(committed);
  expect(user.cell("c3")?.code).toBe("sent");
});

test("keeps the whole draft when another writer deletes an edited cell", async ({
  expect,
  session: { user, host, notebook },
}) => {
  user.changeCode("c3", "keep this");
  const synced = user.sync();
  const request = await host.nextRequest();
  host.deleteCell("c3");
  request.process();
  request.deliverResponse();
  host.deliverDocument();
  await expect(synced).rejects.toThrow("conflict");

  user.changeCode("c1", "other edit");
  await expect(user.retry()).rejects.toThrow("unavailable");
  await vi.advanceTimersByTimeAsync(1000);
  expect(notebook.edit).toHaveBeenCalledOnce();
  expect(host.document().cells.get("c1")?.code).toBe("import marimo as mo");

  host.createCell({ id: "c3", code: "restored" });
  host.deliverDocument();
  expect(user.cell("c3")?.code).toBe("keep this");
  const retried = user.retry();
  const retry = await host.nextRequest();
  retry.process();
  retry.deliverResponse();
  host.deliverDocument();
  await expect(retried).resolves.toEqual(host.document().revision);
  expect(host.document().cells.get("c3")?.code).toBe("keep this");
  expect(host.document().cells.get("c1")?.code).toBe("other edit");
});
