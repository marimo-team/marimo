/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, waitFor } from "@testing-library/react";
import {
  createNotebookReducer,
  type NotebookClient,
  type Result,
  uiElements,
} from "@marimo-team/client";
import type {
  EventOutput,
  NotebookOutput,
  UIElementUpdateResponseOutput,
} from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { registerReactComponent } from "@/plugins/core/registerReactComponent";
import { SliderPlugin } from "@/plugins/impl/SliderPlugin";
import { Deferred } from "@/utils/Deferred";
import { fakeBackend } from "../../notebook/replica/__tests__/fixtures";
import { createUIElementModel } from "../../notebook/ui-elements/model";
import { MarimoValueReadyEvent } from "../events";
import { initializeUIElement } from "../ui-element";
import { UI_ELEMENT_REGISTRY as registry } from "../uiregistry";

SetupMocks.resizeObserver();
beforeAll(() => {
  initializeUIElement();
  registerReactComponent(new SliderPlugin());
});
afterEach(() => {
  act(() => document.querySelector("marimo-ui-element")?.remove());
  act(() => document.body.replaceChildren());
  registry.entries.clear();
});

it("mounts from host state, keeps newer input visible, and sends no legacy write", async () => {
  const store = createStore();
  const reducer = createNotebookReducer({ uiElements });
  let state = reducer.initial;
  const uiElementsAtom = atom(uiElements.initial);
  const replies: Deferred<Result<UIElementUpdateResponseOutput>>[] = [];
  const update = vi.fn<NotebookClient["updateUIElement"]>(() => {
    const reply = new Deferred<Result<UIElementUpdateResponseOutput>>();
    replies.push(reply);
    return reply.promise;
  });
  const replica = {
    uiElementsAtom,
    backendAtom: atom(fakeBackend({ updateUIElement: update })),
    notebookAtom: atom<NotebookOutput | null>({
      id: "n1",
      project_id: "p1",
      name: "Notebook",
      path: null,
      updated_at: null,
      operations: ["ui_element.update"],
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
  const legacy = vi.fn();
  document.addEventListener(MarimoValueReadyEvent.TYPE, legacy);
  function receive(event: EventOutput) {
    act(() => {
      state = reducer.reduce(state, event);
      store.set(uiElementsAtom, state.resources.uiElements);
    });
  }
  const element = {
    id: "c1-0",
    kind: "element" as const,
    cell_id: "c1",
    config: { component: "marimo-slider", label: null, args: {} },
    state: { value: 3 },
  };
  const create = () =>
    receive({ event: "ui_element", data: { ui_element: element } });
  try {
    create();
    act(() => {
      const template = document.createElement("template");
      template.innerHTML = `<marimo-ui-element object-id="c1-0"><marimo-slider data-initial-value="1" data-start="0" data-stop="10" data-step="1" data-steps="null" data-label="null"></marimo-slider></marimo-ui-element>`;
      document.body.append(template.content);
    });
    const slider = document.querySelector("marimo-slider");
    const thumb = () => slider?.shadowRoot?.querySelector('[role="slider"]');
    await waitFor(() => expect(thumb()).toHaveAttribute("aria-valuenow", "3"));
    const mountedThumb = thumb();
    expect(mountedThumb).not.toBeNull();
    if (!mountedThumb) {
      throw new Error("Slider did not mount");
    }
    fireEvent.keyDown(mountedThumb, { key: "ArrowRight" });
    fireEvent.keyDown(mountedThumb, { key: "ArrowRight" });
    expect(update).toHaveBeenCalledTimes(2);
    expect(thumb()).toHaveAttribute("aria-valuenow", "5");
    const firstKey = update.mock.calls[0][2]?.idempotencyKey;
    receive({
      event: "ui_element.update",
      data: {
        id: element.id,
        state: { value: 4 },
        request_id: firstKey,
        time: "2026-11-03T00:00:00Z",
      },
    });
    expect(thumb()).toHaveAttribute("aria-valuenow", "5");
    receive({
      event: "ui_element.update",
      data: {
        id: element.id,
        state: { value: 5 },
        request_id: update.mock.calls[1][2]?.idempotencyKey,
        time: "2026-11-03T00:00:00Z",
      },
    });
    receive({
      event: "ui_element.update",
      data: {
        id: element.id,
        state: { value: 7 },
        time: "2026-11-03T00:00:00Z",
      },
    });
    expect(thumb()).toHaveAttribute("aria-valuenow", "7");
    receive({ event: "reset", data: {} });
    create();
    expect(thumb()).toHaveAttribute("aria-valuenow", "3");
    expect(legacy).not.toHaveBeenCalled();
    await act(async () => {
      replies.forEach((reply, index) =>
        reply.resolve({
          ok: true,
          status: 202,
          data: {
            id: element.id,
            state: { value: index + 4 },
            request_id: update.mock.calls[index][2]?.idempotencyKey ?? "",
          },
        }),
      );
    });
    expect(thumb()).toHaveAttribute("aria-valuenow", "3");
    act(() => store.set(replica.notebookAtom, null));
    fireEvent.keyDown(mountedThumb, { key: "ArrowRight" });
    await waitFor(() => expect(thumb()).toHaveAttribute("aria-valuenow", "3"));
    expect(update).toHaveBeenCalledTimes(2);
  } finally {
    document.removeEventListener(MarimoValueReadyEvent.TYPE, legacy);
    disconnect();
    lifetime.abort();
  }
});
