/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai/vanilla";
import { test as baseTest, vi } from "vitest";
import type { Document } from "../../host/resources/document";
import { createDocumentModel } from "../model";
import { initialDocument } from "./protocol-fixtures";
import { createTestNotebook } from "./test-notebook";
import { createUser } from "./user";

function createSession(initial: Document, controller: AbortController) {
  const store = createStore();
  const { notebook, control } = createTestNotebook(store, initial);
  const model = createDocumentModel({
    store,
    documentAtom: notebook.documentAtom,
    backendAtom: notebook.backendAtom,
    signal: controller.signal,
  });
  return {
    user: createUser(store, model),
    host: control,
    notebook,
    controller,
  };
}

export const test = baseTest.extend<{
  initial: Document;
  session: ReturnType<typeof createSession>;
}>({
  initial: initialDocument(),
  session: async ({ initial }, provide) => {
    vi.useFakeTimers({ now: 0 });
    const controller = new AbortController();
    try {
      await provide(createSession(initial, controller));
    } finally {
      controller.abort();
      vi.useRealTimers();
    }
  },
});
