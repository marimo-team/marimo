/* Copyright 2026 Marimo. All rights reserved. */

import { history, undo } from "@codemirror/commands";
import { EditorSelection, EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { CellId } from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cellId as brandedCellId } from "@/__tests__/branded";
import { createNotebookActions } from "@/core/cells/cells";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { cellActionsState } from "../../codemirror/cells/state";
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
import { SCHEMA_CACHE } from "../../codemirror/language/languages/sql/completion-store";
import type { Document } from "../../host/resources/document";
import { cellCodeBinding } from "../codemirror";
import { createDocumentModel } from "../model";
import { fakeBackend } from "../../host/__tests__/fixtures";
import { cell, document, withCells } from "./fixtures";

const views: EditorView[] = [];
const lifetimes: AbortController[] = [];

afterEach(() => {
  for (const view of views.splice(0)) {
    view.destroy();
  }
  lifetimes.splice(0).forEach((controller) => controller.abort());
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
    cellActionsState.of({
      ...createNotebookActions(vi.fn()),
      toggleHideCode: () => false,
      aiCellCompletion: () => false,
      createManyBelow: vi.fn(),
      addOrAppendSetupCell: vi.fn(),
      onRun: vi.fn(),
      deleteCell: vi.fn(),
      afterToggleMarkdown: vi.fn(),
      afterToggleSQL: vi.fn(),
      saveNotebook: vi.fn(),
    }),
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
  const controller = new AbortController();
  lifetimes.push(controller);
  const model = createDocumentModel({
    store,
    documentAtom: source,
    backendAtom: atom(fakeBackend({ edit: () => new Promise(() => {}) })),
    signal: controller.signal,
  });
  const editor = (text = doc) => {
    const view = new EditorView({
      state: EditorState.create({
        doc: text,
        extensions: [
          history(),
          adapters ? languages(cellId) : [],
          cellCodeBinding({ store, model, cellId }),
        ],
      }),
    });
    views.push(view);
    return view;
  };
  const view = editor();
  return {
    store,
    source,
    model,
    view,
    editor,
    code: () => store.get(model.documentAtom)?.cells.get(cellId)?.code,
    status: () => store.get(model.syncStatusAtom),
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
    const { view, status } = setup();
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1");
    expect(undo(view)).toBe(false);
    expect(status()).toEqual({ status: "idle" });
  });

  it("writes local changes to the draft before the update returns", async () => {
    const { code, status, type } = setup();
    await settle();
    type(" + 1");
    expect(code()).toBe("x = 1 + 1");
    expect(status()).toEqual({ status: "pending" });
  });

  it("shows a change another subscriber makes while a push notifies", async () => {
    const { store, model, view, type } = setup();
    await settle();
    // Another subscriber normalizes code synchronously, inside the push.
    const unsubscribe = store.sub(model.documentAtom, () => {
      const code = store.get(model.documentAtom)?.cells.get("c1")?.code;
      if (code?.includes(" + ")) {
        const normalized = code.replaceAll(" + ", "+");
        store.set(model.editAtom, (tx) => tx.setCode("c1", normalized));
      }
    });
    type(" + 1");
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1+1");
    unsubscribe();
  });

  it("keeps the selection between separate host edits", async () => {
    const { store, source, view } = setup({
      initial: withCells(document(), { c1: cell("c1", "a = 1\nb = 2\nc = 3") }),
    });
    await settle();
    view.dispatch({ selection: EditorSelection.cursor(8) });

    store.set(
      source,
      withCells(document(), { c1: cell("c1", "A = 1\nb = 2\nC = 3") }),
    );
    await settle();

    expect(view.state.doc.toString()).toBe("A = 1\nb = 2\nC = 3");
    expect(view.state.selection.main.head).toBe(8);
  });

  it("waits for composition to end before applying host changes", async () => {
    const { store, source, view } = setup();
    await settle();
    let composing = true;
    Object.defineProperty(view, "composing", { get: () => composing });

    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1");

    // A composition can end without an update, so the binding watches for it.
    composing = false;
    view.contentDOM.dispatchEvent(new Event("compositionend"));
    await settle();
    expect(view.state.doc.toString()).toBe("x = 2");
  });

  it("applies a waiting host change on the first update after composition", async () => {
    const { store, source, view } = setup();
    await settle();
    let composing = true;
    Object.defineProperty(view, "composing", { get: () => composing });
    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    await settle();

    composing = false;
    view.dispatch({ selection: EditorSelection.cursor(0) });
    await settle();
    expect(view.state.doc.toString()).toBe("x = 2");
  });

  it("keeps two editors on one cell in step", async () => {
    const { editor, type } = setup();
    const other = editor();
    await settle();

    type("!");
    await settle();

    expect(other.state.doc.toString()).toBe("x = 1!");
  });

  it("shows host code that returns to what this editor wrote", async () => {
    const { store, source, view, type } = setup();
    await settle();
    type("!");
    // The host confirms the edit, which releases the draft.
    store.set(source, withCells(document(), { c1: cell("c1", "x = 1!") }));
    await settle();

    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    await settle();
    expect(view.state.doc.toString()).toBe("x = 2");

    store.set(source, withCells(document(), { c1: cell("c1", "x = 1!") }));
    await settle();
    expect(view.state.doc.toString()).toBe("x = 1!");
  });

  it("follows a cell once its code is available", async () => {
    const absent = setup({ cellId: "c3" });
    const withheld = setup({
      initial: withCells(document(), { c1: cell("c1", "", { code: null }) }),
    });
    await settle();

    absent.store.set(
      absent.source,
      withCells(document(), { c3: cell("c3", "new") }),
    );
    withheld.store.set(
      withheld.source,
      withCells(document(), { c1: cell("c1", "revealed") }),
    );
    await settle();

    expect(absent.view.state.doc.toString()).toBe("new");
    expect(withheld.view.state.doc.toString()).toBe("revealed");
  });

  it("shows the host's code after typing while the document was unavailable", async () => {
    const { store, source, view, type, code } = setup();
    await settle();

    // All in one task, so no pull runs while the document is away.
    store.set(source, null);
    type(" + 1");
    store.set(source, document());
    await settle();

    expect(view.state.doc.toString()).toBe(code());
  });

  it("leaves the editor alone for an absent cell or withheld source", async () => {
    const absent = setup({ cellId: "c9", doc: "local" });
    const withheld = setup({
      initial: withCells(document(), { c1: cell("c1", "", { code: null }) }),
      doc: "local",
    });
    await settle();

    for (const { view, type, status } of [absent, withheld]) {
      type("!");
      expect(view.state.doc.toString()).toBe("local!");
      expect(status()).toEqual({ status: "idle" });
    }
  });

  it("stops following the cell when the view is destroyed", async () => {
    const { store, source, view } = setup();
    await settle();

    // The change arrives before the view goes, and would apply just after.
    store.set(source, withCells(document(), { c1: cell("c1", "x = 2") }));
    view.destroy();
    await settle();

    expect(view.state.doc.toString()).toBe("x = 1");
  });

  describe("with language adapters", () => {
    const language = (view: EditorView) =>
      view.state.field(languageAdapterState).type;
    /** What the editor's adapter reads back from cell code. */
    const readBack = (view: EditorView, code: string | null | undefined) => {
      const [text, , metadata] = view.state
        .field(languageAdapterState)
        .transformIn(code ?? "");
      return { text, metadata };
    };

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
      expect(readBack(view, code())).toMatchObject({
        text: "hi {x}!",
        metadata: { quotePrefix: "f" },
      });
    });

    it("switches language for host code without rewriting it", async () => {
      const { store, source, view, code, status } = setup({ adapters: true });
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
      expect(status()).toEqual({ status: "idle" });
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
      expect(readBack(view, code())).toMatchObject({
        text: "# Title",
        metadata: { quotePrefix: "r" },
      });
    });

    it("applies a host change to language metadata alone", async () => {
      const { store, source, view } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'mo.md(r"""hi""")'),
        }),
      });
      await settle();

      store.set(
        source,
        withCells(document(), { c1: cell("c1", 'mo.md(f"""hi""")') }),
      );
      await settle();

      expect(view.state.doc.toString()).toBe("hi");
      expect(view.state.field(languageMetadataField)).toMatchObject({
        quotePrefix: "f",
      });
    });

    it("does not rewrite code when the editor switches language as it opens", async () => {
      const original = 'mo.md("hello")';
      const { view, code, status } = setup({
        adapters: true,
        doc: original,
        initial: withCells(document(), { c1: cell("c1", original) }),
      });
      // The cell editor switches to the language its code implies on mount.
      switchLanguage(view, { language: "markdown" });
      await settle();

      expect(code()).toBe(original);
      expect(status()).toEqual({ status: "idle" });
    });

    it("keeps typed text that the adapter would normalize", async () => {
      const { view, type } = setup({
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
      expect(readBack(view, code())).toMatchObject({
        text: "SELECT 1 LIMIT 1",
        metadata: { dataframeName: "df" },
      });
    });

    it("sets the SQL dialect from the host's engine", async () => {
      const { store, source } = setup({ adapters: true });
      await settle();
      const dialect = vi.spyOn(SCHEMA_CACHE, "getDialect");
      try {
        store.set(
          source,
          withCells(document(), {
            c1: cell("c1", '_df = mo.sql(f"""SELECT 1""", engine=warehouse)'),
          }),
        );
        await settle();
        expect(dialect).toHaveBeenLastCalledWith("warehouse");

        store.set(
          source,
          withCells(document(), {
            c1: cell("c1", '_df = mo.sql(f"""SELECT 1""", engine=lake)'),
          }),
        );
        await settle();
        expect(dialect).toHaveBeenLastCalledWith("lake");
      } finally {
        dialect.mockRestore();
      }
    });
  });
});
