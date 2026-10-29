/* Copyright 2026 Marimo. All rights reserved. */

import { atom, type createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import {
  createDocumentModel,
  type DocumentModel,
  DocumentProvider,
} from "@/core/notebook/document";
import { document as documentFixture } from "@/core/notebook/document/__tests__/fixtures";
import type { Document } from "@/core/notebook/replica";
import { fakeBackend } from "@/core/notebook/replica/__tests__/fixtures";

/** A started document model over `document`, for components that edit cells. */
export function mockDocumentModel(
  store: ReturnType<typeof createStore>,
  document: Document | null = documentFixture(),
): { model: DocumentModel; stop: () => void } {
  const controller = new AbortController();
  const model = createDocumentModel({
    store,
    documentAtom: atom(document),
    backendAtom: atom(fakeBackend()),
  });
  model.start({ signal: controller.signal });
  return { model, stop: () => controller.abort() };
}

/** Provide `store` and `model` to a rendered hook or component. */
export function DocumentWrapper({
  store,
  model,
  children,
}: {
  store: ReturnType<typeof createStore>;
  model: DocumentModel;
  children?: ReactNode;
}) {
  return (
    <Provider store={store}>
      <DocumentProvider model={model}>{children}</DocumentProvider>
    </Provider>
  );
}
