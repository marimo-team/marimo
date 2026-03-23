/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { LoroDoc, LoroText } from "loro-crdt";
import { describe, expect, it, vi } from "vitest";
import { LoroSyncPluginValue, loroSyncAnnotation } from "../sync";

describe("LoroSyncPluginValue", () => {
  it("annotates the initial reconciliation dispatch as RTC sync", async () => {
    const dispatch = vi.fn();
    const view = {
      state: EditorState.create({ doc: "local" }),
      dispatch,
    } as unknown as EditorView;

    const doc = new LoroDoc();
    const text = doc
      .getMap("codes")
      .getOrCreateContainer("cell-1", new LoroText());
    text.insert(0, "remote");

    const plugin = new LoroSyncPluginValue(
      view,
      doc,
      ["codes", "cell-1"],
      () => text,
    );

    await Promise.resolve();

    expect(dispatch).toHaveBeenCalledTimes(1);
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        changes: [
          {
            from: 0,
            to: view.state.doc.length,
            insert: "remote",
          },
        ],
        annotations: [
          expect.objectContaining({
            type: loroSyncAnnotation,
          }),
        ],
      }),
    );

    plugin.destroy();
  });
});
