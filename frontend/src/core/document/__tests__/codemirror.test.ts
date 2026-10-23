/* Copyright 2026 Marimo. All rights reserved. */

import { history, undo } from "@codemirror/commands";
import { EditorSelection, EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { CellId } from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it } from "vitest";
import { cellId as brandedCellId } from "@/__tests__/branded";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { cellConfigExtension } from "../../codemirror/config/extension";
import {
  adaptiveLanguageConfiguration,
  languageAdapterState,
  switchLanguage,
} from "../../codemirror/language/extension";
import {
  languageMetadataField,
  setLanguageMetadata,
} from "../../codemirror/language/metadata";
import type { Document } from "../../host/resources/document";
import { cellCodeBinding } from "../codemirror";
import { createDocumentModel } from "../model";
import { cell, document, withCells } from "./fixtures";

const views: EditorView[] = [];

afterEach(() => {
  for (const view of views.splice(0)) {
    view.destroy();
  }
});

const completionConfig = {
  activate_on_typing: true,
  signature_hint_on_typing: false,
  copilot: false,
  codeium_api_key: null,
} as const;

/** The language configuration a marimo cell editor installs. */
function languages(id: CellId) {
  const options = {
    cellId: brandedCellId(id),
    completionConfig,
    hotkeys: new OverridingHotkeyProvider({}),
    placeholderType: "marimo-import",
    lspConfig: {},
  } as const;
  return [
    adaptiveLanguageConfiguration(options),
    cellConfigExtension({ ...options, diagnosticsConfig: {} }),
  ];
}

function setup({
  initial = document(),
  cellId = "c1",
  doc = "",
  adapters = false,
}: {
  initial?: Document | null;
  cellId?: CellId;
  doc?: string;
  adapters?: boolean;
} = {}) {
  const store = createStore();
  const source = atom(initial);
  const model = createDocumentModel(store, source);
  const view = new EditorView({
    state: EditorState.create({
      doc,
      extensions: [
        history(),
        adapters ? languages(cellId) : [],
        cellCodeBinding({ store, model, cellId }),
      ],
    }),
  });
  views.push(view);
  return {
    store,
    source,
    model,
    view,
    code: () => store.get(model.cellAtom(cellId))?.code,
    changes: () => store.get(model.changesAtom),
    type: (insert: string) =>
      view.dispatch({
        changes: { from: view.state.doc.length, insert },
        userEvent: "input.type",
      }),
  };
}

// Inbound changes apply in a microtask.
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe("cellCodeBinding", () => {
  it("seeds the editor from the cell outside undo history", async () => {
    const { view, changes } = setup();
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1");
    expect(undo(view)).toBe(false);
    expect(changes()).toEqual([]);
  });

  it("writes local changes to the draft before the update returns", async () => {
    const { code, changes, type } = setup();
    await settle();
    type(" + 1");
    expect(code()).toBe("x = 1 + 1");
    expect(changes()).toHaveLength(1);
  });

  it("applies host changes as a minimal edit that maps the selection", async () => {
    const { store, source, view, changes } = setup();
    await settle();
    view.dispatch({ selection: EditorSelection.cursor(1) });

    store.set(source, withCells(document(), { c1: cell("c1", "# n\nx = 1") }));
    await settle();

    expect(view.state.doc.toString()).toBe("# n\nx = 1");
    expect(view.state.selection.main.head).toBe(5);
    expect(undo(view)).toBe(false);
    expect(changes()).toEqual([]);
  });

  it("keeps local code when the host changes a cell with a draft", async () => {
    const { store, source, view, type } = setup();
    await settle();
    type(" + 1");

    store.set(source, withCells(document(), { c1: cell("c1", "z = 9") }));
    await settle();

    expect(view.state.doc.toString()).toBe("x = 1 + 1");
  });

  it("waits for composition to end before applying host changes", async () => {
    const { store, source, view } = setup();
    await settle();
    let composing = true;
    Object.defineProperty(view, "composing", { get: () => composing });

    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1");

    composing = false;
    view.dispatch({});
    await settle();
    expect(view.state.doc.toString()).toBe("x = 2");
  });

  it("leaves the editor alone for an absent cell or withheld source", async () => {
    const absent = setup({ cellId: "c9", doc: "local" });
    const withheld = setup({
      initial: withCells(document(), { c1: cell("c1", "", { code: null }) }),
      doc: "local",
    });
    await settle();

    for (const { view, type, changes } of [absent, withheld]) {
      type("!");
      expect(view.state.doc.toString()).toBe("local!");
      expect(changes()).toEqual([]);
    }
  });

  it("stops following the cell when the view is destroyed", async () => {
    const { store, source, view } = setup();
    await settle();
    view.destroy();

    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    await settle();

    expect(view.state.doc.toString()).toBe("x = 1");
  });

  describe("with language adapters", () => {
    const language = (view: EditorView) =>
      view.state.field(languageAdapterState).type;

    it("edits markdown as markdown and writes Python with its metadata", async () => {
      const { view, code, type } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'mo.md(f"""hi {x}""")'),
        }),
      });
      await settle();
      expect(language(view)).toBe("markdown");
      expect(view.state.doc.toString()).toBe("hi {x}");

      type("!");
      expect(code()).toBe('mo.md(f"""\nhi {x}!\n""")');
    });

    it("switches language for host code without rewriting it", async () => {
      const { store, source, view, code, changes } = setup({ adapters: true });
      await settle();
      expect(language(view)).toBe("python");

      store.set(
        source,
        withCells(document(), { c1: cell("c1", 'mo.md("hi")') }),
      );
      await settle();

      expect(language(view)).toBe("markdown");
      expect(view.state.doc.toString()).toBe("hi");
      expect(code()).toBe('mo.md("hi")');
      expect(changes()).toEqual([]);
    });

    it("writes changes to language metadata alone", async () => {
      const { view, code } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'mo.md("""\n# Title\n""")'),
        }),
      });
      await settle();

      view.dispatch({
        effects: setLanguageMetadata.of({
          ...view.state.field(languageMetadataField),
          quotePrefix: "r",
        }),
      });
      expect(code()).toBe('mo.md(r"""\n# Title\n""")');
    });

    it("keeps typed text that the adapter would normalize", async () => {
      const { view, code, type } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'mo.md("""\nhi\n""")'),
        }),
      });
      await settle();

      type("\n");
      await settle();
      type(" ");
      await settle();

      expect(view.state.doc.toString()).toBe("hi\n ");
      expect(code()).toBe('mo.md("""\nhi\n \n""")');
    });

    it("keeps the language a person chose when the cell changes otherwise", async () => {
      const { store, model, view } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'mo.md("""\nhi\n""")'),
        }),
      });
      await settle();
      switchLanguage(view, { language: "python" });
      await settle();

      store.set(model.editAtom, (tx) => tx.setName("c1", "renamed"));
      await settle();

      expect(language(view)).toBe("python");
    });

    it("edits SQL as SQL and keeps its output name", async () => {
      const { store, source, view, code, type } = setup({ adapters: true });
      await settle();

      store.set(
        source,
        withCells(document(), {
          c1: cell("c1", 'df = mo.sql(f"""SELECT 1""")'),
        }),
      );
      await settle();
      expect(language(view)).toBe("sql");
      expect(view.state.doc.toString()).toBe("SELECT 1");

      type(" LIMIT 1");
      expect(code()).toBe(
        'df = mo.sql(\n    f"""\n    SELECT 1 LIMIT 1\n    """\n)',
      );
    });
  });
});
