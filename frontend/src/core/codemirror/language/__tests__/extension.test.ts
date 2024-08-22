/* Copyright 2024 Marimo. All rights reserved. */
import { beforeAll, describe, expect, it } from "vitest";
import {
  adaptiveLanguageConfiguration,
  getInitialLanguageAdapter,
} from "../extension";
import { EditorState } from "@codemirror/state";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { MovementCallbacks } from "../../cells/extensions";
import { store } from "@/core/state/jotai";
import { capabilitiesAtom } from "@/core/config/capabilities";

function createState(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      adaptiveLanguageConfiguration({
        completionConfig: {
          copilot: false,
          activate_on_typing: true,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        enableAI: true,
        showPlaceholder: true,
        cellMovementCallbacks: {} as MovementCallbacks,
      }),
    ],
  });

  return state;
}

describe("getInitialLanguageAdapter", () => {
  beforeAll(() => {
    store.set(capabilitiesAtom, {
      sql: true,
      terminal: true,
    });
  });

  it("should return python", () => {
    let state = createState("def f():\n  return 1");
    expect(getInitialLanguageAdapter(state).type).toBe("python");

    state = createState("");
    expect(getInitialLanguageAdapter(state).type).toBe("python");
  });

  it("should return markdown", () => {
    const state = createState("mo.md('hello')");
    expect(getInitialLanguageAdapter(state).type).toBe("markdown");
  });

  it("should return sql", () => {
    const state = createState("df = mo.sql('hello')");
    expect(getInitialLanguageAdapter(state).type).toBe("sql");
  });
});
