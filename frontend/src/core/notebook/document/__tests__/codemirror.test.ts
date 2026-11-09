/* Copyright 2026 Marimo. All rights reserved. */

import { defaultUserConfig } from "@/core/config/config-schema";

import { history, undo } from "@codemirror/commands";
import { MySQL, PostgreSQL } from "@codemirror/lang-sql";
import { language as activeLanguage } from "@codemirror/language";
import { EditorSelection, EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { CellId } from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cellId as brandedCellId } from "@/__tests__/branded";
import { createNotebookActions } from "@/core/cells/cells";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { cellActionsState } from "../../../codemirror/cells/state";
import { cellConfigExtension } from "../../../codemirror/config/extension";
import {
  adaptiveLanguageConfiguration,
  languageAdapterState,
  switchLanguage,
} from "../../../codemirror/language/extension";
import {
  languageMetadataField,
  setLanguageMetadata,
} from "../../../codemirror/language/metadata";
import {
  editorShowsCellCode,
  getCellCode,
} from "../../../codemirror/language/cell-code";
import { SCHEMA_CACHE } from "../../../codemirror/language/languages/sql/completion-store";
import type { Document } from "../../replica/resources/document";
import { cellCodeBinding } from "../codemirror";
import { createDocumentModel } from "../model";
import { fakeBackend } from "../../replica/__tests__/fixtures";
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
  ...defaultUserConfig().completion,
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
    lspConfig: { ...defaultUserConfig().language_servers },
  } as const;
  return [
    cellActionsState.of({
      ...createNotebookActions(vi.fn()),
      toggleHideCode: () => false,
      askAiAboutCell: () => undefined,
      aiCellCompletion: () => false,
      createManyBelow: vi.fn(),
      addOrAppendSetupCell: vi.fn(),
      setCellCode: vi.fn(),
      createCell: vi.fn(),
      moveToNextCell: vi.fn(),
      addSetupCell: vi.fn(),
      deleteCells: vi.fn(),
      undoDeleteCell: vi.fn(),
      focusCell: vi.fn(),
      focusTopCell: vi.fn(),
      focusBottomCell: vi.fn(),
      collapseCell: vi.fn(),
      expandCell: vi.fn(),
      collapseAllCells: vi.fn(),
      expandAllCells: vi.fn(),
      clearCellOutput: vi.fn(),
      clearAllCellOutputs: vi.fn(),
      showCellIfHidden: vi.fn(),
      moveCell: vi.fn(),
      moveCellToIndex: vi.fn(),
      moveCellsRelativeTo: vi.fn(),
      dropCellOverCell: vi.fn(),
      dropCellOverColumn: vi.fn(),
      sendToTop: vi.fn(),
      sendToBottom: vi.fn(),
      addColumn: vi.fn(),
      addColumnBreakpoint: vi.fn(),
      deleteColumn: vi.fn(),
      mergeAllColumns: vi.fn(),
      compactColumns: vi.fn(),
      moveColumn: vi.fn(),
      splitCell: vi.fn(),
      undoSplitCell: vi.fn(),
      onRun: vi.fn(),
      deleteCell: vi.fn(),
      afterToggleMarkdown: vi.fn(),
      afterToggleSQL: vi.fn(),
      saveNotebook: vi.fn(),
    }),
    adaptiveLanguageConfiguration(options),
    cellConfigExtension({
      ...options,
      diagnosticsConfig: { ...defaultUserConfig().diagnostics },
    }),
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
  const model = createDocumentModel({
    store,
    documentAtom: source,
    backendAtom: atom(fakeBackend({ edit: () => new Promise(() => {}) })),
  });
  const controller = new AbortController();
  lifetimes.push(controller);
  model.start({ signal: controller.signal });
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

    it("keeps Python mode for host code without rewriting it", async () => {
      const { store, source, view, code, status } = setup({ adapters: true });
      await settle();
      expect(language(view)).toBe("python");

      store.set(
        source,
        withCells(document(), { c1: cell("c1", 'mo.md("hi")') }),
      );
      await settle();

      expect(language(view)).toBe("python");
      expect(view.state.doc.toString()).toBe('mo.md("hi")');
      expect(code()).toBe('mo.md("hi")');
      expect(status()).toEqual({ status: "idle" });
    });

    it("keeps Python mode while typing mo.md() and receiving its echo", async () => {
      const { store, source, view, type } = setup({
        adapters: true,
        initial: withCells(document(), { c1: cell("c1", "") }),
      });
      await settle();
      type("mo.md");
      await settle();
      type("()");
      await settle();
      store.set(source, withCells(document(), { c1: cell("c1", "mo.md()") }));
      await settle();

      expect(language(view)).toBe("python");
      expect(view.state.doc.toString()).toBe("mo.md()");
    });

    it("falls back to Python when host code no longer fits Markdown", async () => {
      const { store, source, view, code, status } = setup({
        adapters: true,
        initial: withCells(document(), { c1: cell("c1", 'mo.md("hi")') }),
      });
      await settle();
      expect(language(view)).toBe("markdown");

      store.set(source, withCells(document(), { c1: cell("c1", "x = 1") }));
      await settle();

      expect(language(view)).toBe("python");
      expect(view.state.doc.toString()).toBe("x = 1");
      expect(code()).toBe("x = 1");
      expect(status()).toEqual({ status: "idle" });
    });

    it("preserves Python when typing before the initial pull", async () => {
      const { view, type } = setup({
        adapters: true,
        initial: withCells(document(), { c1: cell("c1", "") }),
      });
      type("mo.md()");
      await settle();

      expect(language(view)).toBe("python");
      expect(view.state.doc.toString()).toBe("mo.md()");
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
      const { view, code, type } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'df = mo.sql(f"""SELECT 1""")'),
        }),
      });
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
      const { store, source, view } = setup({
        adapters: true,
        initial: withCells(document(), {
          c1: cell("c1", 'df = mo.sql("SELECT 1")'),
        }),
      });
      await Promise.resolve();
      const getDialect = SCHEMA_CACHE.getDialect.bind(SCHEMA_CACHE);
      const dialects = new Map([
        ["warehouse", PostgreSQL],
        ["lake", MySQL],
      ]);
      const dialect = vi
        .spyOn(SCHEMA_CACHE, "getDialect")
        .mockImplementation(
          (engine) => dialects.get(engine) ?? getDialect(engine),
        );
      try {
        store.set(
          source,
          withCells(document(), {
            c1: cell("c1", '_df = mo.sql(f"""SELECT 1""", engine=warehouse)'),
          }),
        );
        await Promise.resolve();
        expect(view.state.facet(activeLanguage)).toBe(PostgreSQL.language);

        store.set(
          source,
          withCells(document(), {
            c1: cell("c1", '_df = mo.sql(f"""SELECT 1""", engine=lake)'),
          }),
        );
        await Promise.resolve();
        expect(view.state.facet(activeLanguage)).toBe(MySQL.language);
      } finally {
        dialect.mockRestore();
      }
    });
  });
});

describe("cellCodeBinding before the cell has source", () => {
  it("still infers the language when the source first arrives", async () => {
    const { store, view, source, type } = setup({
      initial: null,
      adapters: true,
    });
    type("x");
    await settle();
    store.set(source, withCells(document(), { c1: cell("c1", 'mo.md("hi")') }));
    await settle();
    expect(view.state.field(languageAdapterState).type).toBe("markdown");
  });
});

describe("cellCodeBinding under random interleavings", () => {
  // A small deterministic generator, so a failure names the seed to replay.
  function generator(seed: number) {
    let state = seed >>> 0;
    return () => {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 2 ** 32;
    };
  }

  const TOKENS = ["x", " ", "\n", "= 1", "mo.md(", ")", '"""', "#", "y + 2"];
  const REMOTE = [
    "x = 2",
    'mo.md(r"""hi""")',
    "y = x + 1\nz = y",
    "",
    "# other",
  ];

  async function stress(seed: number, adapters: boolean) {
    const random = generator(seed);
    const pick = <T>(items: readonly T[]) =>
      items[Math.floor(random() * items.length)];
    const { store, source, model, view, editor, code } = setup({
      adapters,
      initial: withCells(document(), { c1: cell("c1", "x = 1") }),
    });
    const other = editor();
    await settle();
    let composing = false;
    Object.defineProperty(view, "composing", { get: () => composing });
    let version = 1;
    let hostCode = "x = 1";
    const host = (next: string | null) => {
      version += 1;
      store.set(
        source,
        withCells(document(), {
          c1:
            next === null
              ? null
              : cell("c1", next, { version, etag: `c1-${version}` }),
        }),
      );
    };
    const agrees = (state = view.state) => {
      const current = code();
      return typeof current !== "string" || editorShowsCellCode(state, current);
    };
    // Every write to the model is one local or host step. A binding that
    // echoed its own pulls back as pushes would write many more.
    let writes = 0;
    let steps = 0;
    // Checks inside the loop collect here, so one assertion reports them all.
    const failures: string[] = [];
    const check = (label: string, ok: boolean) => {
      if (!ok) {
        failures.push(label);
      }
    };
    const unsubscribe = store.sub(model.documentAtom, () => {
      writes += 1;
    });

    for (let step = 0; step < 200; step++) {
      const roll = random();
      steps += 1;
      if (roll < 0.35) {
        const length = view.state.doc.length;
        const from = Math.floor(random() * (length + 1));
        view.dispatch({
          changes: { from, insert: pick(TOKENS) },
          userEvent: "input.type",
        });
        // A local change reaches the model before the update returns.
        check(`step ${step} after typing`, agrees());
      } else if (roll < 0.45) {
        const length = view.state.doc.length;
        if (length > 0) {
          const from = Math.floor(random() * length);
          const to = Math.min(length, from + 1 + Math.floor(random() * 5));
          view.dispatch({
            changes: { from, to },
            userEvent: "delete.backward",
          });
          check(`step ${step} after deleting`, agrees());
        }
      } else if (roll < 0.6) {
        // The host confirms what this client wrote.
        const current = code();
        if (typeof current === "string") {
          hostCode = current;
          host(hostCode);
        }
      } else if (roll < 0.75) {
        // Another client changes the cell.
        hostCode = pick(REMOTE);
        host(hostCode);
      } else if (roll < 0.8) {
        // The cell leaves the document and returns.
        host(null);
        await settle();
        host(hostCode);
      } else if (roll < 0.88) {
        composing = !composing;
        if (!composing) {
          view.contentDOM.dispatchEvent(new Event("compositionend"));
        }
      } else if (roll < 0.94) {
        other.dispatch({
          changes: { from: other.state.doc.length, insert: pick(TOKENS) },
          userEvent: "input.type",
        });
      } else if (roll < 0.97) {
        // The host withholds the cell's source for a while.
        version += 1;
        store.set(
          source,
          withCells(document(), {
            c1: cell("c1", "", { code: null, version, etag: `c1-${version}` }),
          }),
        );
      } else {
        // The document goes away and comes back.
        store.set(source, null);
        await settle();
        host(hostCode);
      }
      if (random() < 0.5) {
        await settle();
        check(`step ${step} after settling`, composing || agrees());
        check(`step ${step} other editor`, agrees(other.state));
      }
    }
    unsubscribe();
    check(`${writes} writes for ${steps} steps`, writes <= 2 * steps);

    composing = false;
    view.contentDOM.dispatchEvent(new Event("compositionend"));
    host(hostCode);
    await settle();
    await settle();
    const current = code();
    check("cell present at the end", typeof current === "string");
    check("editor agrees at the end", agrees());
    check("other editor agrees at the end", agrees(other.state));
    // Without adapters the agreement is plain text equality.
    check(
      "text equal at the end",
      adapters || getCellCode(view.state) === current,
    );
    return failures;
  }

  const seeds = Array.from({ length: 16 }, (_, i) => i + 1);
  for (const seed of seeds) {
    it(`keeps editor and model in agreement, seed ${seed}`, async () => {
      expect(await stress(seed, false)).toEqual([]);
    });
  }
  for (const seed of seeds) {
    it(`keeps editor and model in agreement with language adapters, seed ${seed}`, async () => {
      expect(await stress(seed, true)).toEqual([]);
    });
  }
});
