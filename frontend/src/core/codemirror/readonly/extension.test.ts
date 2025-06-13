/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { WebSocketState } from "@/core/websocket/types";
import { connectionAtom } from "../../network/connection";
import { dynamicReadonly, isEditorReadonly } from "./extension";

function makeStoreWithConnection(
  state: WebSocketState.CONNECTING | WebSocketState.OPEN,
) {
  const store = createStore();
  store.set(connectionAtom, { state });
  return store;
}

describe("dynamicReadonly", () => {
  it("should be readonly when connection is not OPEN", () => {
    const store = makeStoreWithConnection(WebSocketState.CONNECTING);
    const state = EditorState.create({
      doc: "test",
      extensions: [dynamicReadonly(store)],
    });
    expect(isEditorReadonly(state)).toBe(true);
  });

  it("should be editable when connection is OPEN", async () => {
    const store = makeStoreWithConnection(WebSocketState.OPEN);
    const state = EditorState.create({
      doc: "test",
      extensions: [dynamicReadonly(store)],
    });
    await new Promise((resolve) => setTimeout(resolve, 2));
    expect(isEditorReadonly(state)).toBe(false);
  });

  it("should toggle readonly when connection state changes", () => {
    const store = makeStoreWithConnection(WebSocketState.CONNECTING);
    const state = EditorState.create({
      doc: "test",
      extensions: [dynamicReadonly(store)],
    });
    const view = new EditorView({ state });
    expect(isEditorReadonly(state)).toBe(true);
    // Simulate connection opening
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    // The extension uses a plugin to update the state, so we need to create a view to trigger it
    view.requestMeasure();
    // The state should now be editable
    expect(isEditorReadonly(view.state)).toBe(false);
    view.destroy();
  });
});
