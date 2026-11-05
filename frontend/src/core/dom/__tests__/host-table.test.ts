/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, waitFor } from "@testing-library/react";
import {
  createNotebookReducer,
  type NotebookClient,
  uiElements,
} from "@marimo-team/client";
import type { EventOutput, NotebookOutput } from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { registerReactComponent } from "@/plugins/core/registerReactComponent";
import { DataTablePlugin } from "@/plugins/impl/DataTablePlugin";
import { fakeBackend } from "../../notebook/replica/__tests__/fixtures";
import { createUIElementModel } from "../../notebook/ui-elements/model";
import { MarimoValueReadyEvent } from "../events";
import { initializeUIElement } from "../ui-element";
import { UI_ELEMENT_REGISTRY as registry } from "../uiregistry";

SetupMocks.resizeObserver();
beforeAll(() => {
  initializeUIElement();
  registerReactComponent(DataTablePlugin);
});
afterEach(() => {
  act(() => document.body.replaceChildren());
  registry.entries.clear();
});

it("routes mounted table search and selection through the shared host binding", async () => {
  const store = createStore();
  const reducer = createNotebookReducer({ uiElements });
  let state = reducer.initial;
  const uiElementsAtom = atom(uiElements.initial);
  const data = [{ value: "apple" }, { value: "banana" }];
  const send = vi.fn<NotebookClient["sendUIElement"]>(async (_id, message) => {
    expect(message.function).toBe("search");
    return {
      ok: true,
      status: 200,
      data: {
        request_id: "search",
        result: {
          found: true,
          status: { code: "ok", title: null, message: null },
          return_value: {
            data,
            total_rows: 2,
            cell_styles: null,
            cell_hover_texts: null,
          },
        },
      },
    };
  });
  const update = vi.fn<NotebookClient["updateUIElement"]>(
    async (id, state, options) => ({
      ok: true,
      status: 202,
      data: { id, state, request_id: options?.idempotencyKey ?? "" },
    }),
  );
  const replica = {
    uiElementsAtom,
    backendAtom: atom(
      fakeBackend({ updateUIElement: update, sendUIElement: send }),
    ),
    notebookAtom: atom<NotebookOutput | null>({
      id: "n1",
      project_id: "p1",
      name: "Notebook",
      path: null,
      updated_at: null,
      operations: ["ui_element.update", "ui_element.send"],
    }),
  };
  const model = createUIElementModel({ store, replica });
  const lifetime = new AbortController();
  model.start({ signal: lifetime.signal });
  const disconnect = registry.connectHost({
    values: () => store.get(model.valuesAtom),
    subscribe: (fn) => store.sub(model.valuesAtom, fn),
    update: model.update,
  });
  const disconnectFunctions = registry.connectFunctions(model.functionRequest);
  const legacy = vi.fn();
  document.addEventListener(MarimoValueReadyEvent.TYPE, legacy);
  function receive(event: EventOutput) {
    act(() => {
      state = reducer.reduce(state, event);
      store.set(uiElementsAtom, state.resources.uiElements);
    });
  }
  try {
    receive({
      event: "ui_element",
      data: {
        ui_element: {
          id: "c1-0",
          kind: "element",
          cell_id: "c1",
          config: { component: "marimo-table", label: null, args: {} },
          state: { value: [] },
        },
      },
    });
    const tables: HTMLElement[] = [];
    act(() => {
      for (let i = 0; i < 2; i++) {
        const wrapper = document.createElement("marimo-ui-element");
        wrapper.setAttribute("object-id", "c1-0");
        wrapper.setAttribute("random-id", `view-${i}`);
        const table = document.createElement("marimo-table");
        for (const [key, value] of Object.entries({
          initialValue: [],
          label: null,
          data,
          totalRows: 2,
          totalColumns: 1,
          rowHeaders: [],
          selection: "multi",
          pagination: false,
          showColumnSummaries: false,
          showColumnExplorer: false,
          showChartBuilder: false,
          showDownload: false,
          showSearch: false,
          showDataTypes: false,
        })) {
          table.dataset[key] = JSON.stringify(value);
        }
        wrapper.append(table);
        document.body.append(wrapper);
        tables.push(table);
      }
    });
    const checkboxes = (i: number) =>
      tables[i].shadowRoot!.querySelectorAll<HTMLElement>('[role="checkbox"]');
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(checkboxes(0).length).toBeGreaterThan(1));
    fireEvent.click(checkboxes(0)[1]);
    await waitFor(() => expect(update).toHaveBeenCalled());
    const latest = update.mock.calls.at(-1)!;
    expect(latest[0]).toBe("c1-0");
    expect(latest[1]).toEqual({ value: ["0"] });
    expect(legacy).not.toHaveBeenCalled();
    receive({
      event: "ui_element.update",
      data: {
        id: "c1-0",
        state: { value: ["0"] },
        request_id: latest[2]?.idempotencyKey,
        time: "2026-11-04T00:00:00Z",
      },
    });
    await waitFor(() =>
      expect(checkboxes(1)[1]).toHaveAttribute("aria-checked", "true"),
    );
    receive({
      event: "ui_element.update",
      data: {
        id: "c1-0",
        state: { value: ["1"] },
        time: "2026-11-04T00:00:01Z",
      },
    });
    for (const i of [0, 1]) {
      await waitFor(() =>
        expect(checkboxes(i)[2]).toHaveAttribute("aria-checked", "true"),
      );
      expect(checkboxes(i)[1]).toHaveAttribute("aria-checked", "false");
    }
  } finally {
    act(() => document.body.replaceChildren());
    document.removeEventListener(MarimoValueReadyEvent.TYPE, legacy);
    disconnectFunctions();
    disconnect();
    lifetime.abort();
  }
});
