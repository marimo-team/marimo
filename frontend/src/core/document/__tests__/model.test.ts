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
    expect(sent.mock.calls[0][0].signal.aborted).toBe(true);
    expect(status()).toMatchObject({ status: "error", retryable: false });
  });
});
