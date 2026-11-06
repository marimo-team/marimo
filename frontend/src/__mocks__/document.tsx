/* Copyright 2026 Marimo. All rights reserved. */

import { atom, type createStore, type PrimitiveAtom, Provider } from "jotai";
import type { ReactNode } from "react";
import {
  createDocumentModel,
  type DocumentModel,
  DocumentProvider,
} from "@/core/notebook/document";
import { document as documentFixture } from "@/core/notebook/document/__tests__/fixtures";
import type { Document } from "@/core/notebook/replica";
import { fakeBackend } from "@/core/notebook/replica/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";

/**
 * A started document model over `document`, for components that edit cells.
 * Setting `documentAtom` delivers a document as the host would.
 */
export function mockDocumentModel(
  store: ReturnType<typeof createStore>,
  document: Document | null = documentFixture(),
): {
  model: DocumentModel;
  documentAtom: PrimitiveAtom<Document | null>;
  stop: () => void;
} {
  const controller = new AbortController();
  const documentAtom = atom(document);
  const model = createDocumentModel({
    store,
    documentAtom,
    backendAtom: atom(fakeBackend()),
  });
  model.start({ signal: controller.signal });
  store.set(activeDocumentModelAtom, model);
  return {
    model,
    documentAtom,
    stop: () => {
      controller.abort();
      if (store.get(activeDocumentModelAtom) === model) {
        store.set(activeDocumentModelAtom, null);
      }
    },
  };
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
