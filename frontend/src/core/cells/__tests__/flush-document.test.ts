/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createDocumentModel } from "@/core/notebook/document";
import {
  type FakeEdit,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import type { Document } from "@/core/notebook/replica/resources/document";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { flushDocument } from "../document";

const lifetimes: AbortController[] = [];

afterEach(() => {
  lifetimes.splice(0).forEach((controller) => controller.abort());
  store.set(activeDocumentModelAtom, null);
});

describe("flushDocument", () => {
  it("sends nothing while the document is unavailable", async () => {
    const edit = vi.fn<FakeEdit>();
    const model = createDocumentModel({
      store,
      documentAtom: atom<Document | null>(null),
      backendAtom: atom(fakeBackend({ edit })),
    });
    const controller = new AbortController();
    lifetimes.push(controller);
    model.start({ signal: controller.signal });
    store.set(activeDocumentModelAtom, model);

    expect(store.get(model.syncStatusAtom)).toEqual({ status: "unavailable" });
    await expect(model.flush()).rejects.toThrow("unavailable");
    await expect(flushDocument()).resolves.toBeUndefined();
    expect(edit).not.toHaveBeenCalled();
  });
});
