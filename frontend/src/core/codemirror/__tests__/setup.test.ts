/* Copyright 2026 Marimo. All rights reserved. */

import { defaultUserConfig } from "@/core/config/config-schema";

import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { afterEach, describe, expect, test, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { configOverridesAtom } from "@/core/config/config";
import type { ExperimentalFeatures } from "@/core/config/feature-flag";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import { Objects } from "@/utils/objects";
import type { CodemirrorCellActions } from "../cells/state";
import { type CodeMirrorSetupOpts, setupCodeMirror } from "../cm";
import { PythonLanguageAdapter } from "../language/languages/python";

vi.mock("@/core/config/config", async (importOriginal) => {
  const original = await importOriginal<{}>();
  return {
    ...original,
    parseAppConfig: () => ({}),
    parseUserConfig: () => ({}),
  };
});
vi.mock("@/core/config/config", async (importOriginal) => {
  const original = await importOriginal<{}>();
  return {
    ...original,
    parseAppConfig: () => ({}),
    parseUserConfig: () => ({}),
  };
});

function namedFunction(name: string) {
  const fn = () => false;
  Object.defineProperty(fn, "name", { value: name });
  return fn;
}

function getOpts() {
  return {
    cellId: cellId("0"),
    showPlaceholder: false,
    enableAI: false,
    cellActions: {
      toggleHideCode: namedFunction("toggleHideCode"),
      askAiAboutCell: namedFunction("askAiAboutCell"),
      aiCellCompletion: namedFunction("aiCellCompletion"),
      createManyBelow: namedFunction("createManyBelow"),
      onRun: namedFunction("onRun"),
      deleteCell: namedFunction("deleteCell"),
      afterToggleMarkdown: namedFunction("afterToggleMarkdown"),
      afterToggleSQL: namedFunction("afterToggleSQL"),
    } as unknown as CodemirrorCellActions,
    completionConfig: {
      ...defaultUserConfig().completion,
      activate_on_typing: false,
      signature_hint_on_typing: false,
      copilot: false,
    },
    keymapConfig: {
      preset: "default",
      overrides: {},
    },
    lspConfig: {
      pylsp: {
        ...defaultUserConfig().language_servers.pylsp,
        enabled: false,
      },
      diagnostics: { ...defaultUserConfig().diagnostics, enabled: false },
    },
    diagnosticsConfig: { ...defaultUserConfig().diagnostics },
    hotkeys: new OverridingHotkeyProvider({}),
    theme: "light",
    displayConfig: { reference_highlighting: false, code_lens: true },
    inlineAiTooltip: false,
  } as const;
}

function setup(config: Partial<CodeMirrorSetupOpts> = {}): Extension[] {
  return setupCodeMirror({ ...getOpts(), ...config });
}

function prettyPrintKeymaps(state: EditorState) {
  const keymaps = state.facet(keymap).flat();
  const prettyKeymaps = keymaps.map((keymap) => {
    const { key, run, any, shift, ...rest } = keymap;
    return {
      key: key?.toString(),
      ...(any ? { any: any.name || "<no name>" } : {}),
      ...(run ? { run: run.name || "<no name>" } : {}),
      ...(shift ? { shift: shift.name || "<no name>" } : {}),
      ...rest,
    };
  });
  return prettyKeymaps;
}

function getDuplicateKeymaps(state: EditorState) {
  const prettyKeymaps = prettyPrintKeymaps(state);
  const groupBy = Objects.groupBy(
    prettyKeymaps,
    (keymap) => keymap.key,
    (keymap) => keymap,
  );
  const duplicates = Objects.fromEntries(
    Object.entries(groupBy).filter(([_key, value]) => value.length > 1),
  );
  return duplicates;
}

describe("snapshot all duplicate keymaps", () => {
  // This test just ensures we are not accidentally overlapping keymaps
  // without handling it (precedence or otherwise).

  test("default keymaps", () => {
    const extensions = setup();
    const duplicates = getDuplicateKeymaps(
      EditorState.create({ extensions: extensions }),
    );
    // Total duplicates:
    // if this changes, please make sure to validate they are not conflicting
    expect(Object.values(duplicates).flat().length).toMatchInlineSnapshot("18");
    expect(duplicates).toMatchSnapshot();
  });

  test("vim keymaps", () => {
    const extensions = setup({
      keymapConfig: { preset: "vim", overrides: {} },
    });
    const duplicates = getDuplicateKeymaps(
      EditorState.create({ extensions: extensions }),
    );
    // Total duplicates:
    // if this changes, please make sure to validate they are not conflicting
    expect(Object.values(duplicates).flat().length).toMatchInlineSnapshot("18");
    expect(duplicates).toMatchSnapshot();
  });
});

test("auto_close_pairs: false removes closeBrackets keymaps", () => {
  const withAutoClose = EditorState.create({
    extensions: setup(),
  });
  const withoutAutoClose = EditorState.create({
    extensions: setup({
      completionConfig: {
        ...getOpts().completionConfig,
        auto_close_pairs: false,
      },
    }),
  });

  const keysWith = withAutoClose.facet(keymap).flat();
  const keysWithout = withoutAutoClose.facet(keymap).flat();

  // closeBracketsKeymap contributes Backspace and Enter handlers
  expect(keysWith.length).toBeGreaterThan(keysWithout.length);

  const hasBracketPairHandler = (state: EditorState) =>
    state
      .facet(keymap)
      .flat()
      .some((k) => k.run?.name === "deleteBracketPair");

  expect(hasBracketPairHandler(withAutoClose)).toBe(true);
  expect(hasBracketPairHandler(withoutAutoClose)).toBe(false);
});

test("go to definition falls through to lower-priority LSP keymap", () => {
  const lspGoToDefinition = vi.fn(() => true);
  const goToDefinitionKey = getOpts().hotkeys.getHotkey(
    "cell.goToDefinition",
  ).key;

  const view = new EditorView({
    state: EditorState.create({
      doc: "parser.add_argument('--foo')",
      selection: { anchor: "parser.".length },
      extensions: [
        ...setup(),
        keymap.of([{ key: goToDefinitionKey, run: lspGoToDefinition }]),
      ],
    }),
    parent: document.body,
  });

  try {
    const event = new KeyboardEvent("keydown", {
      key: goToDefinitionKey,
      bubbles: true,
      cancelable: true,
    });
    view.contentDOM.dispatchEvent(event);

    expect(lspGoToDefinition).toHaveBeenCalledOnce();
  } finally {
    view.destroy();
  }
});

test("placeholder adds another extension", () => {
  const opts = getOpts();
  const withAI = new PythonLanguageAdapter()
    .getExtension({
      cellId: opts.cellId,
      completionConfig: opts.completionConfig,
      hotkeys: opts.hotkeys,
      placeholderType: "marimo-import",
      lspConfig: opts.lspConfig,
    })
    .flat();
  const withoutAI = new PythonLanguageAdapter()
    .getExtension({
      cellId: opts.cellId,
      completionConfig: opts.completionConfig,
      hotkeys: opts.hotkeys,
      placeholderType: "none",
      lspConfig: opts.lspConfig,
    })
    .flat();
  expect(withAI.length - 1).toBe(withoutAI.length);
});

test("ai adds more extensions", () => {
  const opts = getOpts();
  const withAI = new PythonLanguageAdapter()
    .getExtension({
      cellId: opts.cellId,
      completionConfig: opts.completionConfig,
      hotkeys: opts.hotkeys,
      placeholderType: "ai",
      lspConfig: opts.lspConfig,
    })
    .flat();
  const withoutAI = new PythonLanguageAdapter()
    .getExtension({
      cellId: opts.cellId,
      completionConfig: opts.completionConfig,
      hotkeys: opts.hotkeys,
      placeholderType: "none",
      lspConfig: opts.lspConfig,
    })
    .flat();
  expect(withAI.length - 2).toBe(withoutAI.length);
});

test("empty-cell AI action opens chat without invoking the local refactor prompt", () => {
  const askAiAboutCell = vi.fn();
  const aiCellCompletion = vi.fn();
  const view = new EditorView({
    state: EditorState.create({
      doc: "",
      extensions: setup({
        showPlaceholder: true,
        enableAI: false,
        enableAIChat: true,
        cellActions: {
          ...getOpts().cellActions,
          askAiAboutCell,
          aiCellCompletion,
        },
      }),
    }),
  });
  try {
    const button = view.dom.querySelector<HTMLButtonElement>(
      ".cm-clickable-placeholder",
    );
    expect(button?.textContent).toBe("generate with AI");
    button?.click();
    expect(askAiAboutCell).toHaveBeenCalledOnce();
    expect(aiCellCompletion).not.toHaveBeenCalled();
  } finally {
    view.destroy();
  }
});

describe("editor styles are shared between cells", () => {
  afterEach(() => {
    store.set(configOverridesAtom, {});
  });

  test.each([
    ["default", {}, {}],
    ["clickable placeholder", { enableAIChat: true }, {}],
    ["debugger", {}, { debugger: true }],
    ["line timing", {}, { line_timing: true }],
  ] satisfies [
    string,
    Partial<CodeMirrorSetupOpts>,
    Partial<ExperimentalFeatures>,
  ][])(
    "no style module is built per editor (%s)",
    (_name, config, experimental) => {
      store.set(configOverridesAtom, { experimental });
      const styleModules = () =>
        EditorState.create({ extensions: setup(config) }).facet(
          EditorView.styleModule,
        );

      const first = styleModules();
      const second = styleModules();

      expect(second).toHaveLength(first.length);
      const perEditor = second.filter((mod, i) => mod !== first[i]);
      expect(perEditor.map((mod) => mod.getRules())).toEqual([]);
    },
  );

  test("mounting another editor does not rewrite the stylesheet", () => {
    const mount = () =>
      new EditorView({
        state: EditorState.create({ extensions: setup() }),
        parent: document.body,
      });
    const first = mount();
    const styleTag = document.head.querySelector("style");
    invariant(styleTag, "CodeMirror did not mount a style tag");
    const observer = new MutationObserver(() => undefined);
    observer.observe(styleTag, { childList: true, characterData: true });

    const second = mount();

    try {
      expect(observer.takeRecords()).toEqual([]);
    } finally {
      observer.disconnect();
      first.destroy();
      second.destroy();
    }
  });
});
