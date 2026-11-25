/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createDocumentModel } from "@/core/notebook/document";
import { document } from "@/core/notebook/document/__tests__/fixtures";
import {
  type FakeEdit,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { DocumentSyncStatus } from "../footer-items/document-sync-status";
import { cellId } from "@/__tests__/branded";

const C1 = cellId("c1");

const lifetimes: AbortController[] = [];

afterEach(() => {
  act(() => lifetimes.splice(0).forEach((controller) => controller.abort()));
});

const conflict = {
  ok: false,
  status: 412,
  problem: {
    type: "urn:marimo:problem:precondition-failed",
    title: "Precondition failed",
    status: 412,
    detail: "cell c1 has changed since it was read.",
    index: 0,
    cell: document().cells.get(C1)!,
    document: document().revision,
  },
} satisfies Awaited<ReturnType<FakeEdit>>;

function setup(edit: FakeEdit) {
  const store = createStore();
  const source = atom(document());
  const model = createDocumentModel({
    store,
    documentAtom: source,
    shownDocumentAtom: source,
    backendAtom: atom(fakeBackend({ edit })),
  });
  const controller = new AbortController();
  lifetimes.push(controller);
  model.start({ signal: controller.signal });
  store.set(activeDocumentModelAtom, model);
  render(
    <Provider store={store}>
      <TooltipProvider>
        <DocumentSyncStatus />
      </TooltipProvider>
    </Provider>,
  );
  return { store, model };
}

describe("DocumentSyncStatus", () => {
  it("renders nothing while edits reach the server", () => {
    setup(vi.fn<FakeEdit>());
    expect(screen.queryByTestId("footer-document-sync")).toBeNull();
  });

  it("shows a rejected edit and resubmits it on click", async () => {
    const accepted = document().revision;
    const edit = vi
      .fn<FakeEdit>()
      .mockResolvedValueOnce(conflict)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: {
          document: { ...accepted, version: 2, etag: "document-2" },
          cells: {},
        },
      });
    const { store, model } = setup(edit);

    await act(async () => {
      store.set(model.editAtom, (tx) => tx.setCode(C1, "x = 2"));
      await model.flush().catch(() => undefined);
    });
    const item = screen.getByTestId("footer-document-sync");
    expect(item).toHaveAttribute(
      "aria-label",
      "Edits are not reaching the server",
    );

    await act(async () => {
      fireEvent.click(item);
      await Promise.resolve();
    });
    expect(edit).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId("footer-document-sync")).toBeNull();
  });
});
