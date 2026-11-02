/* Copyright 2026 Marimo. All rights reserved. */

import { atom, createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Document } from "../../replica/resources/document";
import { createDocumentModel } from "..";
import { type FakeEdit, fakeBackend } from "../../replica/__tests__/fixtures";
import { document } from "./fixtures";

const lifetimes: AbortController[] = [];

afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
});

/** The document after the host accepts one edit. */
function accepted(): Document {
  const base = document();
  return {
    ...base,
    revision: { ...base.revision, version: 2, etag: "document-2" },
  };
}

function setup() {
  const store = createStore();
  const source = atom<Document | null>(document());
  // Answer the edit, then publish the accepted document as the host would.
  const edit = vi.fn<FakeEdit>().mockImplementation(async () => {
    queueMicrotask(() => store.set(source, accepted()));
    return {
      ok: true,
      status: 200,
      data: { document: accepted().revision, cells: {} },
    };
  });
  const model = createDocumentModel({
    store,
    documentAtom: source,
    backendAtom: atom(fakeBackend({ edit })),
  });
  const controller = new AbortController();
  lifetimes.push(controller);
  model.start({ signal: controller.signal });
  return { store, model, edit, controller };
}

describe("document sync hold", () => {
  it("keeps an edit local until released, then lets a waiting flush send it", async () => {
    const { store, model, edit } = setup();
    const release = model.hold();
    store.set(model.editAtom, (tx) => tx.setCode("c1", "x = 2"));
    const flushing = model.flush();
    await Promise.resolve();
    expect(edit).not.toHaveBeenCalled();
    expect(store.get(model.syncStatusAtom)).toEqual({ status: "pending" });

    release();
    await flushing;
    expect(edit).toHaveBeenCalledTimes(1);
  });

  it("releases once the last of nested holds is released", async () => {
    const { store, model, edit } = setup();
    const outer = model.hold();
    const inner = model.hold();
    store.set(model.editAtom, (tx) => tx.setCode("c1", "x = 2"));
    const flushing = model.flush();

    inner();
    inner();
    await Promise.resolve();
    expect(edit).not.toHaveBeenCalled();

    outer();
    await flushing;
    expect(edit).toHaveBeenCalledTimes(1);
  });

  it("rejects a flush waiting on a hold when the model stops", async () => {
    const { store, model, controller } = setup();
    model.hold();
    store.set(model.editAtom, (tx) => tx.setCode("c1", "x = 2"));
    const flushing = model.flush();
    controller.abort(new Error("session ended"));
    await expect(flushing).rejects.toThrow("session ended");
  });
});
