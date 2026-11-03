/* Copyright 2026 Marimo. All rights reserved. */
import {
  createNotebookReducer,
  type Result,
  type NotebookClient,
  uiElements,
} from "@marimo-team/client";
import type {
  EventOutput,
  NotebookOutput,
  UIElementUpdateResponseOutput,
} from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import type { NotebookBackend } from "../../replica";
import { fakeBackend } from "../../replica/__tests__/fixtures";
import { createUIElementModel } from "../model";

function setup() {
  const store = createStore();
  const reducer = createNotebookReducer({ uiElements });
  let state = reducer.initial;
  const uiElementsAtom = atom(uiElements.initial);
  const notebookAtom = atom<NotebookOutput | null>({
    id: "n1",
    project_id: "p1",
    name: "Notebook",
    path: null,
    updated_at: null,
    operations: ["ui_element.update"],
  });
  const replies: Deferred<Result<UIElementUpdateResponseOutput>>[] = [];
  const update = vi.fn<NotebookClient["updateUIElement"]>(() => {
    const reply = new Deferred<Result<UIElementUpdateResponseOutput>>();
    replies.push(reply);
    return reply.promise;
  });
  const backend = fakeBackend({ updateUIElement: update });
  const backendAtom = atom<NotebookBackend | null>(backend);
  const controller = new AbortController();
  const model = createUIElementModel({
    store,
    replica: { uiElementsAtom, notebookAtom, backendAtom },
  });
  model.start({ signal: controller.signal });
  function receive(event: EventOutput) {
    state = reducer.reduce(state, event);
    store.set(uiElementsAtom, state.resources.uiElements);
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
  create();
  function echo(index: number, value: number) {
    const requestId = update.mock.calls[index][2]?.idempotencyKey;
    receive({
      event: "ui_element.update",
      data: {
        id: element.id,
        state: { value },
        request_id: requestId,
        time: "2026-11-03T00:00:00Z",
      },
    });
  }
  function accept(index: number, value: number) {
    replies[index].resolve({
      ok: true,
      status: 202,
      data: {
        id: element.id,
        state: { value },
        request_id: update.mock.calls[index][2]?.idempotencyKey ?? "",
      },
    });
  }
  return {
    store,
    model,
    update,
    replies,
    backendAtom,
    controller,
    receive,
    echo,
    accept,
    create,
    value: () => store.get(model.valuesAtom).get(element.id),
  };
}

describe("UI element drafts", () => {
  it.each(["event-first", "response-first"])(
    "settles the matching draft in %s order",
    async (order) => {
      const s = setup();
      const first = s.model.update("c1-0", 4);
      expect(s.value()).toBe(4);
      const second = s.model.update("c1-0", 5);
      s.echo(0, 4);
      s.accept(0, 4);
      await first;
      expect(s.value()).toBe(5);
      if (order === "event-first") {
        s.echo(1, 5);
      } else {
        s.accept(1, 5);
        await second;
      }
      expect(s.value()).toBe(5);
      if (order === "event-first") {
        s.accept(1, 5);
      } else {
        s.echo(1, 5);
      }
      await second;
      s.receive({
        event: "ui_element.update",
        data: { id: "c1-0", state: { value: 6 }, time: "2026-11-03T00:00:00Z" },
      });
      expect(s.value()).toBe(6);
      s.controller.abort();
    },
  );

  it.each(["reset", "ui_element.removed"] as const)(
    "clears drafts on %s before an id is reused",
    async (event) => {
      const s = setup();
      const pending = s.model.update("c1-0", 5);
      s.receive(
        event === "reset"
          ? { event, data: {} }
          : { event, data: { id: "c1-0", time: "2026-11-03T00:00:00Z" } },
      );
      expect(s.value()).toBeUndefined();
      s.create();
      s.accept(0, 5);
      await pending;
      expect(s.value()).toBe(3);
      s.controller.abort();
    },
  );

  it("binds each submission to its backend and ignores an old rejection", async () => {
    const s = setup();
    const pending = s.model.update("c1-0", 4);
    const replacement = vi.fn();
    s.store.set(s.backendAtom, fakeBackend({ updateUIElement: replacement }));
    s.replies[0].reject(new Error("old backend failed"));
    await expect(pending).rejects.toThrow("old backend failed");
    expect(replacement).not.toHaveBeenCalled();
    expect(s.value()).toBe(3);
    s.controller.abort();
  });
});

it("settles an unchanged value and preserves newer input after an older failure", async () => {
  const s = setup();
  const unchanged = s.model.update("c1-0", 3);
  s.echo(0, 3);
  s.accept(0, 3);
  await unchanged;
  const failed = s.model.update("c1-0", 4);
  const newer = s.model.update("c1-0", 5);
  s.replies[1].reject(new Error("rejected"));
  await expect(failed).rejects.toThrow("rejected");
  expect(s.value()).toBe(5);
  s.echo(2, 5);
  s.accept(2, 5);
  await newer;
  s.receive({
    event: "ui_element.update",
    data: { id: "c1-0", state: { value: 6 }, time: "2026-11-03T00:00:00Z" },
  });
  expect(s.value()).toBe(6);
  s.controller.abort();
});
