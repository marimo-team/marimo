/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { cellConfigExtension } from "../../config/extension";
import {
  adaptiveLanguageConfiguration,
  languageAdapterState,
} from "../../language/extension";
import { realTimeCollaboration } from "../extension";

let view: EditorView | null = null;

afterEach(() => {
  view?.destroy();
  view = null;
});

function createRtcEditor(code: string, id: string) {
  const rtc = realTimeCollaboration(
    cellId(id),
    () => {
      return;
    },
    code,
  );

  view = new EditorView({
    state: EditorState.create({
      doc: rtc.code,
      extensions: [
        adaptiveLanguageConfiguration({
          cellId: cellId(id),
          completionConfig: {
            activate_on_typing: true,
            signature_hint_on_typing: false,
            copilot: false,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          placeholderType: "marimo-import",
          lspConfig: {},
        }),
        cellConfigExtension({
          cellId: cellId(id),
          completionConfig: {
            activate_on_typing: true,
            signature_hint_on_typing: false,
            copilot: false,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          placeholderType: "marimo-import",
          lspConfig: {},
          diagnosticsConfig: {},
        }),
        rtc.extension,
      ],
    }),
  });

  return view;
}

async function settleRtcLanguageInitialization() {
  await Promise.resolve();
  await Promise.resolve();
}

describe("realTimeCollaboration", () => {
  it("initializes new SQL cells from their Python source before local edits", async () => {
    const editor = createRtcEditor(
      'result = mo.sql("""SELECT 1 AS one""")',
      "rtc-sql-created-by-code-mode",
    );

    await settleRtcLanguageInitialization();

    expect(editor.state.field(languageAdapterState).type).toBe("sql");
    expect(editor.state.doc.toString()).toBe("SELECT 1 AS one");
  });

  it("initializes new Markdown cells from their Python source before local edits", async () => {
    const editor = createRtcEditor(
      'mo.md("""# Created live""")',
      "rtc-markdown-created-by-code-mode",
    );

    await settleRtcLanguageInitialization();

    expect(editor.state.field(languageAdapterState).type).toBe("markdown");
    expect(editor.state.doc.toString()).toBe("# Created live");
  });
});
