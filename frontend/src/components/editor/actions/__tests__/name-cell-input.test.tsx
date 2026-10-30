/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import { afterEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  createDocumentModel,
  DocumentProvider,
} from "@/core/notebook/document";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { fakeBackend } from "@/core/notebook/replica/__tests__/fixtures";
import { NameCellContentEditable } from "../name-cell-input";

const controllers: AbortController[] = [];

afterEach(() => {
  for (const controller of controllers.splice(0)) {
    controller.abort();
  }
});

describe("NameCellContentEditable", () => {
  it("renames the cell in the document when the name is committed", () => {
    const store = createStore();
    const source = atom(
      withCells(documentOf(), {
        c1: cell("c1", "x = 1", { name: "first" }),
      }),
    );
    const model = createDocumentModel({
      store,
      documentAtom: source,
      backendAtom: atom(fakeBackend()),
    });
    const controller = new AbortController();
    controllers.push(controller);
    model.start({ signal: controller.signal });

    render(
      <Provider store={store}>
        <DocumentProvider model={model}>
          <TooltipProvider>
            <NameCellContentEditable
              cellId={cellId("c1")}
              value="first"
              className=""
            />
          </TooltipProvider>
        </DocumentProvider>
      </Provider>,
    );

    const field = screen.getByText("first");
    // jsdom does not lay text out, so it has no innerText of its own.
    Object.defineProperty(field, "innerText", { value: " renamed " });
    fireEvent.blur(field);

    expect(store.get(model.documentAtom)?.cells.get("c1")?.name).toBe(
      "renamed",
    );
  });
});
