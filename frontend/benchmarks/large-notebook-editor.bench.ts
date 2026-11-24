/* Copyright 2026 Marimo. All rights reserved. */

import { pythonLanguage } from "@codemirror/lang-python";
import { EditorState, type Extension, StateEffect } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { classHighlighter, highlightTree } from "@lezer/highlight";
import { describe, expect, test } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import type { CodemirrorCellActions } from "@/core/codemirror/cells/state";
import {
  type CodeMirrorSetupOpts,
  setupCodeMirror,
} from "@/core/codemirror/cm";
import {
  getInitialLanguageAdapter,
  languageAdapterFromCode,
  languageAdapterState,
  reconfigureLanguageEffect,
  switchLanguage,
} from "@/core/codemirror/language/extension";
import { defaultUserConfig } from "@/core/config/config-schema";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";

const fast = { time: 500, warmupTime: 200, iterations: 100 };
// Whole-notebook operations take seconds in jsdom; a few samples are enough.
const slow = { time: 0, warmupTime: 0, warmupIterations: 1, iterations: 3 };
const wholeNotebook = { timeout: 300_000 };

// jsdom has no layout. CodeMirror's measure pass logs an error without this.
Object.defineProperty(Range.prototype, "getClientRects", {
  configurable: true,
  value: () => [],
});

const userConfig = defaultUserConfig();
const hotkeys = new OverridingHotkeyProvider({});
const lspConfig = {
  ...userConfig.language_servers,
  diagnostics: userConfig.diagnostics,
};
// The actions are only called from keymaps, which these benchmarks never fire.
const cellActions = {} as CodemirrorCellActions;

/** 32 lines / ~1 KB: the median code cell of the notebook under study. */
function pythonCode(i: number): string {
  const lines = [
    `import inspect as _inspect_r${i}`,
    "",
    `_data_r${i} = {"id": ${i}, "name": "feature_${i}", "tags": ["a", "b"]}`,
  ];
  for (let step = 1; lines.length < 31; step++) {
    lines.push(
      "",
      `# (${step}) The value round-trips through JSON without loss.`,
      `_got_r${i}_${step} = json.loads(json.dumps(_data_r${i}))`,
      `assert _got_r${i}_${step} == _data_r${i}, _got_r${i}_${step}`,
      `assert math.isfinite(_got_r${i}_${step}["id"] + ${step}), (`,
      `    _got_r${i}_${step}`,
      ")",
    );
  }
  return lines.join("\n");
}

function markdownCode(i: number): string {
  return `mo.md(r"""\n## R${i}. \`feature_${i}\` keeps its contract (#${10_000 + i})\n""")`;
}

/** Alternating hidden-code markdown and code cells, as in the notebook. */
function notebook(count: number): Array<{ id: CellId; code: string }> {
  return Array.from({ length: count }, (_, i) => ({
    id: cellId(`bench-${i}`),
    code: i % 2 === 0 ? markdownCode(i) : pythonCode(i),
  }));
}

function setupOptions(id: CellId): CodeMirrorSetupOpts {
  return {
    cellId: id,
    showPlaceholder: false,
    enableAI: false,
    cellActions,
    completionConfig: userConfig.completion,
    keymapConfig: userConfig.keymap,
    lspConfig: userConfig.language_servers,
    diagnosticsConfig: userConfig.diagnostics,
    displayConfig: userConfig.display,
    hotkeys,
    theme: "light",
    inlineAiTooltip: false,
  };
}

/** Mirrors `handleInitializeEditor` in cell-editor.tsx. */
function createEditor(id: CellId, code: string): EditorView {
  const view = new EditorView({
    state: EditorState.create({
      doc: code,
      extensions: setupCodeMirror(setupOptions(id)),
    }),
  });
  switchLanguage(view, {
    language: getInitialLanguageAdapter(view.state).type,
  });
  return view;
}

interface StyleSet {
  modules: unknown[];
  styleTag: HTMLStyleElement;
}

function isStyleSet(value: unknown): value is StyleSet {
  return (
    typeof value === "object" &&
    value !== null &&
    "modules" in value &&
    "styleTag" in value
  );
}

/**
 * CodeMirror never unmounts a style module, and some extensions define a new
 * one for every editor. Without this, each sample would be slower than the
 * last. The set is stored on the document under a symbol private to style-mod.
 */
function resetCodeMirrorStyles(): void {
  for (const symbol of Object.getOwnPropertySymbols(document)) {
    const set: unknown = Reflect.get(document, symbol);
    if (isStyleSet(set)) {
      set.modules.length = 0;
      set.styleTag.textContent = "";
    }
  }
}

/** Mirrors `handleReconfigureEditor` in cell-editor.tsx. */
function reconfigure(view: EditorView, extensions: Extension[]): void {
  view.dispatch({
    effects: [
      StateEffect.reconfigure.of([extensions]),
      reconfigureLanguageEffect(view, {
        completionConfig: userConfig.completion,
        hotkeysProvider: hotkeys,
        lspConfig,
      }),
    ],
  });
}

/** The cheapest faithful stand-in for an unfocused editor: highlighted text. */
function highlightedPre(code: string): HTMLPreElement {
  const pre = document.createElement("pre");
  let position = 0;
  highlightTree(
    pythonLanguage.parser.parse(code),
    classHighlighter,
    (from, to, classes) => {
      if (from > position) {
        pre.append(code.slice(position, from));
      }
      const span = document.createElement("span");
      span.className = classes;
      span.textContent = code.slice(from, to);
      pre.append(span);
      position = to;
    },
  );
  pre.append(code.slice(position));
  return pre;
}

function plainPre(code: string): HTMLPreElement {
  const pre = document.createElement("pre");
  pre.textContent = code;
  return pre;
}

describe("one cell", () => {
  const id = cellId("bench");
  const python = pythonCode(1);
  const markdown = markdownCode(0);
  const extensions = setupCodeMirror(setupOptions(id));

  test("build extensions", async ({ bench }) => {
    await bench("build extensions", () => {
      setupCodeMirror(setupOptions(id));
    }).run(fast);
  });

  test("EditorState.create / python", async ({ bench }) => {
    await bench("EditorState.create / python", () => {
      EditorState.create({ doc: python, extensions });
    }).run(fast);
  });

  test("EditorState.create / markdown source", async ({ bench }) => {
    await bench("EditorState.create / markdown source", () => {
      EditorState.create({ doc: markdown, extensions });
    }).run(fast);
  });

  for (const [language, code] of [
    ["python", python],
    ["markdown", markdown],
  ] as const) {
    test(`extensions + state + view + language / ${language}`, async ({
      bench,
    }) => {
      await bench(
        `extensions + state + view + language / ${language}`,
        {
          beforeAll() {
            const view = createEditor(id, code);
            expect(view.state.field(languageAdapterState).type).toBe(language);
            view.destroy();
          },
          afterEach: resetCodeMirrorStyles,
        },
        () => {
          createEditor(id, code).destroy();
        },
      ).run(fast);
    });
  }

  test("static highlighted <pre>", async ({ bench }) => {
    await bench(
      "static highlighted <pre>",
      {
        beforeAll() {
          expect(highlightedPre(python).textContent).toBe(python);
          expect(highlightedPre(python).children.length).toBeGreaterThan(50);
        },
      },
      () => {
        highlightedPre(python);
      },
    ).run(fast);
  });

  test("plain <pre>", async ({ bench }) => {
    await bench("plain <pre>", () => {
      plainPre(python);
    }).run(fast);
  });
});

for (const count of [50, 500]) {
  describe(`${count} cells / half hidden markdown`, () => {
    const cells = notebook(count);
    let views: EditorView[] = [];

    function mountAll() {
      views = cells.map(({ id, code }) => createEditor(id, code));
    }

    function destroyAll() {
      for (const view of views) {
        view.destroy();
      }
      views = [];
      resetCodeMirrorStyles();
    }

    test("detect language", async ({ bench }) => {
      await bench(
        "detect language",
        {
          beforeAll() {
            const types = cells.map(
              ({ code }) => languageAdapterFromCode(code).type,
            );
            expect(types.filter((type) => type === "markdown")).toHaveLength(
              count / 2,
            );
          },
        },
        () => {
          for (const { code } of cells) {
            languageAdapterFromCode(code);
          }
        },
      ).run(fast);
    });

    test("create every editor", wholeNotebook, async ({ bench }) => {
      await bench(
        "create every editor",
        { afterEach: destroyAll },
        mountAll,
      ).run(slow);
    });

    test("create only the code editors", wholeNotebook, async ({ bench }) => {
      await bench(
        "create only the code editors",
        { afterEach: destroyAll },
        () => {
          views = cells
            .filter((_, i) => i % 2 === 1)
            .map(({ id, code }) => createEditor(id, code));
        },
      ).run(slow);
    });

    test("reconfigure every editor", wholeNotebook, async ({ bench }) => {
      await bench(
        "reconfigure every editor",
        {
          beforeAll: mountAll,
          afterEach: resetCodeMirrorStyles,
          afterAll: destroyAll,
        },
        () => {
          for (const [i, view] of views.entries()) {
            reconfigure(view, setupCodeMirror(setupOptions(cells[i].id)));
          }
        },
      ).run(slow);
    });

    test("one selectionchange event", wholeNotebook, async ({ bench }) => {
      await bench(
        "one selectionchange event",
        { beforeAll: mountAll, afterAll: destroyAll },
        () => {
          document.dispatchEvent(new Event("selectionchange"));
        },
      ).run({ ...fast, warmupTime: 0, iterations: 30 });
    });

    test(
      "static highlighted <pre> for every code cell",
      wholeNotebook,
      async ({ bench }) => {
        await bench("static highlighted <pre> for every code cell", () => {
          for (const [i, { code }] of cells.entries()) {
            if (i % 2 === 1) {
              highlightedPre(code);
            }
          }
        }).run(slow);
      },
    );
  });
}
