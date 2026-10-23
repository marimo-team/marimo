/* Copyright 2026 Marimo. All rights reserved. */

import type { Result } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import type { Document } from "../../host/resources/document";
import { createDocumentModel, type DocumentHost } from "../model";
import { cell, document, withCells } from "./fixtures";

function response(confirmed: Document): Result<Protocol.EditResponseOutput> {
  return {
    ok: true,
    status: 200,
    data: { document: confirmed.revision, cells: {} },
  };
}

// Observe rejections before advancing timers to avoid unhandled promises.
async function expectFailure(promise: Promise<unknown>, message: string) {
  await expect(promise).rejects.toThrow(message);
}

async function expectAbort(promise: Promise<unknown>, reason: Error) {
  await expect(promise).rejects.toBe(reason);
}

/** An edit the host received, with its notebook and options. */
interface SentEdit {
  notebookId: Protocol.NotebookId;
  changes: readonly Protocol.Change[];
  idempotencyKey: string;
  signal: AbortSignal;
}

function setup() {
  const store = createStore();
  const source = atom<Document | null>(document());
  const unmounted = vi.fn();
  source.onMount = () => unmounted;
  const replies: Deferred<Result<Protocol.EditResponseOutput>>[] = [];
  const sent = vi.fn((_edit: SentEdit) => {
    const reply = new Deferred<Result<Protocol.EditResponseOutput>>();
    replies.push(reply);
    return reply.promise;
  });
  const host: DocumentHost = {
    documentAtom: source,
    edit: (notebookId, changes, options) =>
      sent({ notebookId, changes, ...options }),
  };
  const controller = new AbortController();
  lifetimes.push(controller);
  const model = createDocumentModel({
    store,
    notebook: host,
    signal: controller.signal,
  });
  return {
    store,
    source,
    model,
    sent,
    replies,
    controller,
    unmounted,
    edit: (code: string) =>
      store.set(model.editAtom, (tx) => tx.setCode("c1", code)),
    state: () => store.get(model.syncStateAtom),
    value: () => store.get(model.cellAtom("c1")),
  };
}

const lifetimes: AbortController[] = [];
beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
  vi.useRealTimers();
});

describe("document synchronization", () => {
  it("rejects an aborted lifetime before subscribing or sending", () => {
    const store = createStore();
    const source = atom<Document | null>(document());
    const mounted = vi.fn();
    source.onMount = mounted;
    const controller = new AbortController();
    const reason = new Error("Session ended");
    controller.abort(reason);
    const edit = vi.fn<DocumentHost["edit"]>();
    expect(() =>
      createDocumentModel({
        store,
        notebook: { documentAtom: source, edit },
        signal: controller.signal,
      }),
    ).toThrow(reason);
    expect(mounted).not.toHaveBeenCalled();
    expect(edit).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("releases unsent reversals and flushes an unchanged document without a request", async () => {
    const { store, source, sent, edit, model, state, value } = setup();
    edit("temporary");
    edit("x = 1");
    expect(state()).toEqual({ status: "idle" });
    const remote = withCells(document(), { c1: cell("c1", "remote") });
    store.set(source, remote);
    expect(value()?.code).toBe("remote");
    await expect(model.flush()).resolves.toEqual(remote.revision);
    await vi.advanceTimersByTimeAsync(1000);
    expect(sent).not.toHaveBeenCalled();
  });

  it("flushes edits made after an earlier drain finishes but before its promise settles", async () => {
    const { store, source, sent, replies, edit, model } = setup();
    const first = model.flush();
    await Promise.resolve();
    edit("new code");
    const second = model.flush();
    const settled = vi.fn();
    void second.then(settled, settled);

    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toHaveBeenCalledOnce();
    expect(settled).not.toHaveBeenCalled();
    expect(sent.mock.calls[0][0].changes).toMatchObject([
      { cell: { id: "c1", code: "new code" } },
    ]);

    const accepted = withCells(document(), {
      c1: cell("c1", "new code", { etag: "accepted", version: 2 }),
    });
    replies[0].resolve(response(accepted));
    store.set(source, accepted);
    await expect(second).resolves.toEqual(accepted.revision);
    await expect(first).resolves.toEqual(document().revision);
  });

  it("manually retries an uncertain request with its original identity", async () => {
    const { store, source, sent, replies, edit, model } = setup();
    edit("local");
    const flushed = model.flush();
    expect(model.flush()).toBe(flushed);
    const rejected = expectFailure(flushed, "offline");
    await vi.advanceTimersByTimeAsync(0);
    replies[0].reject(new Error("offline"));
    await vi.advanceTimersByTimeAsync(500);
    replies[1].reject(new Error("offline"));
    await vi.advanceTimersByTimeAsync(1000);
    replies[2].reject(new Error("offline"));
    await rejected;
    const retried = model.retry();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent.mock.calls[3][0]).toMatchObject({
      idempotencyKey: sent.mock.calls[0][0].idempotencyKey,
      changes: sent.mock.calls[0][0].changes,
    });
    const accepted = withCells(document(), { c1: cell("c1", "local") });
    replies[3].resolve(response(accepted));
    store.set(source, accepted);
    await expect(retried).resolves.toEqual(accepted.revision);
  });

  it("fails without repeating a request when the response names another notebook", async () => {
    const { sent, replies, edit, model, state } = setup();
    edit("local");
    const rejected = expectFailure(model.flush(), "another notebook");
    await vi.advanceTimersByTimeAsync(0);
    replies[0].resolve(response(document("n2")));
    await rejected;
    await vi.advanceTimersByTimeAsync(5000);
    expect(sent).toHaveBeenCalledOnce();
    expect(state()).toMatchObject({ status: "error" });
  });

  it("debounces typing and waits for streamed confirmation before sending newer edits", async () => {
    const { store, source, sent, replies, edit, model, state, value } = setup();
    edit("first");
    await vi.advanceTimersByTimeAsync(300);
    edit("sent");
    await vi.advanceTimersByTimeAsync(399);
    expect(sent).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(sent).toHaveBeenCalledOnce();
    expect(sent.mock.calls[0][0].changes[0]).toMatchObject({
      cell: { code: "sent" },
    });
    edit("newer");
    const accepted = withCells(document(), {
      c1: cell("c1", "sent", { etag: "accepted" }),
    });
    replies[0].resolve(response(accepted));
    await vi.advanceTimersByTimeAsync(0);
    expect(state()).toEqual({ status: "confirming" });
    await vi.advanceTimersByTimeAsync(1000);
    expect(sent).toHaveBeenCalledOnce();
    store.set(source, accepted);
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toHaveBeenCalledTimes(2);
    expect(sent.mock.calls[1][0].changes[0]).toMatchObject({
      base_etag: "accepted",
      cell: { code: "newer" },
    });
    const latest = withCells(accepted, { c1: cell("c1", "newer") });
    const flushed = model.flush();
    replies[1].resolve(response(latest));
    store.set(source, latest);
    await expect(flushed).resolves.toEqual(latest.revision);
    expect(state()).toEqual({ status: "idle" });
    expect(value()?.code).toBe("newer");
  });

  it.each(["response", "snapshot"] as const)(
    "confirms a reset when %s arrives first without opening a stream",
    async (first) => {
      const { store, source, sent, replies, edit, model } = setup();
      edit("sent");
      const flushed = model.flush();
      await vi.advanceTimersByTimeAsync(0);
      store.set(source, null);
      const accepted = withCells(document(), { c1: cell("c1", "sent") });
      const later = withCells(accepted, { c2: cell("c2", "remote") });
      if (first === "response") {
        replies[0].resolve(response(accepted));
      } else {
        store.set(source, later);
      }
      await vi.advanceTimersByTimeAsync(0);
      expect(store.get(model.syncStateAtom)).toEqual({
        status: first === "response" ? "confirming" : "sending",
      });
      if (first === "response") {
        store.set(source, later);
      } else {
        replies[0].resolve(response(accepted));
      }
      await expect(flushed).resolves.toEqual(later.revision);
      expect(sent).toHaveBeenCalledOnce();
      expect(store.get(model.syncStateAtom)).toEqual({ status: "idle" });
    },
  );

  it("retries a lost response with the captured body and key, preserving subsequent typing", async () => {
    const { store, source, sent, replies, edit, model, value } = setup();
    edit("sent");
    const flushed = model.flush();
    await vi.advanceTimersByTimeAsync(0);
    const accepted = withCells(document(), {
      c1: cell("c1", "sent", { etag: "accepted" }),
    });
    store.set(source, accepted);
    edit("newer");
    replies[0].reject(new Error("response lost"));
    await vi.advanceTimersByTimeAsync(500);
    expect(sent).toHaveBeenCalledTimes(2);
    const original = sent.mock.calls[0][0];
    const retry = sent.mock.calls[1][0];
    expect(retry.idempotencyKey).toBe(original.idempotencyKey);
    expect(retry.changes).toBe(original.changes);
    replies[1].resolve(response(accepted));
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toHaveBeenCalledTimes(3);
    expect(sent.mock.calls[2][0].idempotencyKey).not.toBe(
      original.idempotencyKey,
    );
    const latest = withCells(accepted, { c1: cell("c1", "newer") });
    store.set(source, latest);
    replies[2].resolve(response(latest));
    await expect(flushed).resolves.toEqual(latest.revision);
    expect(value()?.code).toBe("newer");
  });

  it("exposes conflicts and only retries explicitly against a fresh confirmed revision", async () => {
    const { store, source, sent, replies, edit, model, state, value } = setup();
    edit("local");
    const flushed = model.flush();
    const rejected = expectFailure(flushed, "conflict");
    await vi.advanceTimersByTimeAsync(0);
    const remote = withCells(document(), {
      c1: cell("c1", "remote", { etag: "remote" }),
    });
    const problem: Protocol.Problem = {
      type: "tag:marimo.io,2026:host/conflict",
      title: "conflict",
      status: 409,
      edit: {
        change: 0,
        cell: remote.cells.get("c1")!,
        document: remote.revision,
      },
    };
    replies[0].resolve({ ok: false, status: 409, problem });
    await rejected;
    expect(state()).toMatchObject({
      status: "error",
      problem,
      retryable: true,
    });
    await expect(model.retry()).rejects.toThrow("Wait for the host");
    edit("updated local");
    store.set(source, remote);
    await vi.advanceTimersByTimeAsync(2000);
    expect(sent).toHaveBeenCalledOnce();
    expect(value()?.code).toBe("updated local");
    const retry = model.retry();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent.mock.calls[1][0].changes[0]).toMatchObject({
      base_etag: "remote",
      cell: { code: "updated local" },
    });
    const accepted = withCells(remote, { c1: cell("c1", "updated local") });
    replies[1].resolve(response(accepted));
    store.set(source, accepted);
    await expect(retry).resolves.toEqual(accepted.revision);
  });

  it("retains a draft after remote deletion and never sends the other edits alone", async () => {
    const { store, source, model, sent, replies, edit } = setup();
    edit("keep this");
    const flushed = model.flush();
    const rejected = expectFailure(flushed, "removed");
    await vi.advanceTimersByTimeAsync(0);
    const removed = withCells(document(), { c1: null });
    store.set(source, removed);
    replies[0].resolve({
      ok: false,
      status: 409,
      problem: {
        type: "tag:marimo.io,2026:host/conflict",
        title: "removed",
        status: 409,
        edit: { change: 0, cell: null, document: removed.revision },
      },
    });
    await rejected;
    store.set(model.editAtom, (tx) => tx.setCode("c2", "other edit"));
    await expect(model.retry()).rejects.toThrow("unavailable");
    expect(sent).toHaveBeenCalledOnce();
    store.set(source, withCells(removed, { c1: cell("c1", "restored") }));
    expect(store.get(model.cellAtom("c1"))?.code).toBe("keep this");
  });

  it("bounds retries and never replays an uncertain write after receipt expiry", async () => {
    const { sent, replies, edit, model, state } = setup();
    edit("local");
    const flushed = model.flush();
    const rejected = expectFailure(flushed, "offline");
    await vi.advanceTimersByTimeAsync(0);
    replies[0].reject(new Error("offline"));
    await vi.advanceTimersByTimeAsync(500);
    replies[1].reject(new Error("offline"));
    await vi.advanceTimersByTimeAsync(1000);
    replies[2].reject(new Error("offline"));
    await rejected;
    expect(state()).toMatchObject({ status: "error", retryable: true });
    await vi.advanceTimersByTimeAsync(60_000);
    await expect(model.retry()).rejects.toThrow("retry window expired");
    expect(sent).toHaveBeenCalledTimes(3);
    expect(state()).toMatchObject({ status: "error", retryable: false });
  });

  it("times out a hung attempt, aborts it, and retries the same request", async () => {
    const { store, source, sent, replies, edit, model } = setup();
    edit("local");
    const flushed = model.flush();
    await vi.advanceTimersByTimeAsync(10_500);
    expect(sent).toHaveBeenCalledTimes(2);
    expect(sent.mock.calls[0][0].signal.aborted).toBe(true);
    expect(sent.mock.calls[1][0].idempotencyKey).toBe(
      sent.mock.calls[0][0].idempotencyKey,
    );
    const accepted = withCells(document(), { c1: cell("c1", "local") });
    replies[1].resolve(response(accepted));
    store.set(source, accepted);
    await expect(flushed).resolves.toEqual(accepted.revision);
  });

  it("aborts before the debounce without sending any edits", async () => {
    const { sent, edit, model, controller } = setup();
    edit("local");
    controller.abort();
    await vi.advanceTimersByTimeAsync(1000);
    expect(sent).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    await expect(model.flush()).rejects.toThrow("aborted");
  });

  it.each(["request", "confirmation", "retry"] as const)(
    "aborts during %s without leaving work or subscriptions",
    async (phase) => {
      const {
        store,
        source,
        sent,
        replies,
        edit,
        model,
        controller,
        unmounted,
      } = setup();
      edit("local");
      const flushed = model.flush();
      const reason = new Error("Editing session ended");
      const rejected = expectAbort(flushed, reason);
      await vi.advanceTimersByTimeAsync(0);
      if (phase === "confirmation") {
        replies[0].resolve(
          response(withCells(document(), { c1: cell("c1", "local") })),
        );
      }
      if (phase === "retry") {
        replies[0].reject(new Error("offline"));
      }
      await vi.advanceTimersByTimeAsync(0);
      controller.abort(reason);
      await rejected;
      expect(unmounted).toHaveBeenCalledOnce();
      expect(sent).toHaveBeenCalledOnce();
      store.set(source, withCells(document(), { c1: cell("c1", "later") }));
      edit("after disposal");
      expect(vi.getTimerCount()).toBe(0);
      await expect(model.flush()).rejects.toBe(reason);
      await expect(model.retry()).rejects.toBe(reason);
    },
  );

  it("ignores a late response and source update after its lifetime ends", async () => {
    const {
      store,
      source,
      model,
      replies,
      sent,
      edit,
      controller,
      unmounted,
      value,
    } = setup();
    edit("local");
    const reason = new Error("Editing session ended");
    const rejected = expectAbort(model.flush(), reason);
    await vi.advanceTimersByTimeAsync(0);
    controller.abort(reason);
    await rejected;
    const accepted = withCells(document(), { c1: cell("c1", "local") });
    replies[0].resolve(response(accepted));
    store.set(source, accepted);
    const staleEdit = vi.fn();
    store.set(model.editAtom, staleEdit);
    await vi.advanceTimersByTimeAsync(1000);
    expect(unmounted).toHaveBeenCalledOnce();
    expect(staleEdit).not.toHaveBeenCalled();
    expect(value()).toBeUndefined();
    expect(sent).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("rejects a queued flush when aborted before submission", async () => {
    const { model, edit, sent, controller } = setup();
    edit("local");
    const reason = new Error("Editing session ended");
    const rejected = expectAbort(model.flush(), reason);
    controller.abort(reason);
    await rejected;
    expect(sent).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts an in-flight edit when notebook identity changes", async () => {
    const { store, source, sent, edit, model, state } = setup();
    edit("local");
    const flushed = model.flush();
    const rejected = expectFailure(flushed, "notebook changed");
    await vi.advanceTimersByTimeAsync(0);
    store.set(source, document("n2"));
    await rejected;
    expect(sent.mock.calls[0][0].signal.aborted).toBe(true);
    expect(state()).toMatchObject({ status: "error", retryable: false });
  });
});
