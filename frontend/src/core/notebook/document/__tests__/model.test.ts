/* Copyright 2026 Marimo. All rights reserved. */

import type { Result } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import type { NotebookBackend } from "../../replica/backend";
import type { Document } from "../../replica/resources/document";
import { createDocumentModel } from "../model";
import { type FakeEdit, fakeBackend } from "../../replica/__tests__/fixtures";
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
  idempotencyKey?: string;
  signal?: AbortSignal;
}

function setup({ connected = true } = {}) {
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
  const backend = fakeBackend({
    edit: (notebookId, changes, options) =>
      sent({ notebookId, changes, ...options }),
  });
  const backendAtom = atom<NotebookBackend | null>(connected ? backend : null);
  const model = createDocumentModel({
    store,
    documentAtom: source,
    backendAtom,
  });
  const controller = new AbortController();
  lifetimes.push(controller);
  model.start({ signal: controller.signal });
  return {
    store,
    source,
    backend,
    backendAtom,
    model,
    sent,
    replies,
    controller,
    unmounted,
    edit: (code: string) =>
      store.set(model.editAtom, (tx) => tx.setCode("c1", code)),
    status: () => store.get(model.syncStatusAtom),
    value: () => store.get(model.documentAtom)?.cells.get("c1"),
  };
}

const lifetimes: AbortController[] = [];
beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
  vi.useRealTimers();
});

describe("document synchronization", () => {
  it("subscribes to nothing until started", async () => {
    const store = createStore();
    const source = atom<Document | null>(document());
    const mounted = vi.fn();
    source.onMount = mounted;
    const edit = vi.fn<FakeEdit>();
    const model = createDocumentModel({
      store,
      documentAtom: source,
      backendAtom: atom(fakeBackend({ edit })),
    });
    store.set(model.editAtom, (tx) => tx.setCode("c1", "local"));
    await expect(model.flush()).rejects.toThrow("not started");
    expect(store.get(model.documentAtom)).toBeNull();
    expect(store.get(model.syncStatusAtom)).toEqual({ status: "unavailable" });
    expect(mounted).not.toHaveBeenCalled();
    expect(edit).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("rejects an aborted signal before subscribing", () => {
    const store = createStore();
    const source = atom<Document | null>(document());
    const mounted = vi.fn();
    source.onMount = mounted;
    const model = createDocumentModel({
      store,
      documentAtom: source,
      backendAtom: atom(fakeBackend({ edit: vi.fn<FakeEdit>() })),
    });
    const reason = new Error("Session ended");
    expect(() => model.start({ signal: AbortSignal.abort(reason) })).toThrow(
      reason,
    );
    expect(mounted).not.toHaveBeenCalled();
  });

  it("starts again after a subscriber aborts during startup", async () => {
    const store = createStore();
    const model = createDocumentModel({
      store,
      documentAtom: atom(document()),
      backendAtom: atom(null),
    });
    const controller = new AbortController();
    lifetimes.push(controller);
    const unsubscribe = store.sub(model.documentAtom, () => {
      if (store.get(model.documentAtom)) {
        controller.abort();
      }
    });
    model.start({ signal: controller.signal });
    unsubscribe();
    expect(controller.signal.aborted).toBe(true);
    expect(store.get(model.documentAtom)).toBeNull();
    await expect(model.flush()).rejects.toThrow("not started");

    const next = new AbortController();
    lifetimes.push(next);
    model.start({ signal: next.signal });
    expect(store.get(model.documentAtom)?.cells.get("c1")?.code).toBe("x = 1");
  });

  it("starts again without the drafts of a stopped run", () => {
    const { store, model, controller, edit, value } = setup();
    expect(() => model.start({ signal: new AbortController().signal })).toThrow(
      "already started",
    );
    edit("local");
    controller.abort();
    const next = new AbortController();
    lifetimes.push(next);
    model.start({ signal: next.signal });
    expect(value()?.code).toBe("x = 1");
    store.set(model.editAtom, (tx) => tx.setCode("c1", "restarted"));
    expect(value()?.code).toBe("restarted");
  });

  it("fails without repeating a request when the response names another notebook", async () => {
    const { sent, replies, edit, model, status } = setup();
    edit("local");
    const rejected = expectFailure(model.flush(), "another notebook");
    await vi.advanceTimersByTimeAsync(0);
    replies[0].resolve(response(document("n2")));
    await rejected;
    await vi.advanceTimersByTimeAsync(5000);
    expect(sent).toHaveBeenCalledOnce();
    expect(status()).toMatchObject({ status: "error" });
  });

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

  it("aborts an in-flight edit when notebook identity changes", async () => {
    const { store, source, sent, edit, model, status } = setup();
    edit("local");
    const flushed = model.flush();
    const rejected = expectFailure(flushed, "notebook changed");
    await vi.advanceTimersByTimeAsync(0);
    store.set(source, document("n2"));
    await rejected;
    expect(sent.mock.calls[0][0].signal?.aborted).toBe(true);
    expect(status()).toMatchObject({ status: "error", retryable: false });
  });

  it("aborts an in-flight edit when the backend changes and never sends it to the new one", async () => {
    const { store, backendAtom, sent, edit, model } = setup();
    edit("local");
    const rejected = expectFailure(model.flush(), "notebook changed");
    await vi.advanceTimersByTimeAsync(0);
    const other = vi.fn<FakeEdit>();
    store.set(backendAtom, fakeBackend({ edit: other }));
    await rejected;
    expect(sent).toHaveBeenCalledOnce();
    expect(sent.mock.calls[0][0].signal?.aborted).toBe(true);
    expect(other).not.toHaveBeenCalled();
  });

  it("keeps edits as drafts until a backend is connected", async () => {
    const { store, backend, backendAtom, sent, edit, status, value } = setup({
      connected: false,
    });
    edit("local");
    await vi.advanceTimersByTimeAsync(1000);
    expect(status()).toEqual({ status: "unavailable" });
    expect(value()?.code).toBe("local");

    store.set(backendAtom, backend);
    await vi.advanceTimersByTimeAsync(400);
    expect(sent).toHaveBeenCalledOnce();
  });
});
