/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createDocumentModel } from "@/core/notebook/document";
import { document } from "@/core/notebook/document/__tests__/fixtures";
import type { Document } from "@/core/notebook/replica/resources/document";
import {
  type FakeEdit,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { Deferred } from "@/utils/Deferred";
import { withDocumentSave } from "../document";

const lifetimes: AbortController[] = [];

afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
  store.set(activeDocumentModelAtom, null);
});

describe("withDocumentSave", () => {
  it("sends an edit made during the save only after the save finishes", async () => {
    const source = atom<Document | null>(document());
    const base = document();
    const accepted: Document = {
      ...base,
      revision: { ...base.revision, version: 2, etag: "document-2" },
    };
    // Answer the edit, then publish the accepted document as the host would.
    const edit = vi.fn<FakeEdit>().mockImplementation(async () => {
      queueMicrotask(() => store.set(source, accepted));
      return {
        ok: true,
        status: 200,
        data: { document: accepted.revision, cells: {} },
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
    store.set(activeDocumentModelAtom, model);

    const saving = new Deferred<void>();
    let flushing: Promise<unknown> | undefined;
    const saved = withDocumentSave(async () => {
      store.set(model.editAtom, (tx) => tx.setCode("c1", "x = 2"));
      flushing = model.flush();
      await Promise.resolve();
      expect(edit).not.toHaveBeenCalled();
      await saving.promise;
      return "saved";
    });

    saving.resolve();
    await expect(saved).resolves.toBe("saved");
    await flushing;
    expect(edit).toHaveBeenCalledTimes(1);
  });
});
