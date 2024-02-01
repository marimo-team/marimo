/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test, vi } from "vitest";
import { CodeMirrorSetupOpts, setupCodeMirror } from "../cm";
import { EditorState, Extension } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { CellId } from "@/core/cells/ids";
import { Objects } from "@/utils/objects";

vi.mock("@/core/config/config", () => ({
  parseAppConfig: () => ({}),
  parseUserConfig: () => ({}),
}));

function namedFunction(name: string) {
  const fn = () => false;
  Object.defineProperty(fn, "name", { value: name });
  return fn;
}

function setup(config: Partial<CodeMirrorSetupOpts> = {}): Extension[] {
  return setupCodeMirror({
    cellId: "0" as CellId,
    showPlaceholder: false,
    cellMovementCallbacks: {
      onRun: namedFunction("onRun"),
      deleteCell: namedFunction("deleteCell"),
      createAbove: namedFunction("createAbove"),
      createBelow: namedFunction("createBelow"),
      moveUp: namedFunction("moveUp"),
      moveDown: namedFunction("moveDown"),
      focusUp: namedFunction("focusUp"),
      focusDown: namedFunction("focusDown"),
      sendToTop: namedFunction("sendToTop"),
      sendToBottom: namedFunction("sendToBottom"),
      moveToNextCell: namedFunction("moveToNextCell"),
      toggleHideCode: namedFunction("toggleHideCode"),
    },
    cellCodeCallbacks: {
      updateCellCode: namedFunction("updateCellCode"),
    },
    completionConfig: {
      activate_on_typing: false,
      copilot: false,
    },
    keymapConfig: {
      preset: "default",
    },
    theme: "light",
    ...config,
  });
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
    Object.entries(groupBy).filter(([key, value]) => value.length > 1),
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
    expect(Object.values(duplicates).flat().length).toMatchInlineSnapshot(`20`);
    expect(duplicates).toMatchSnapshot();
  });

  test("vim keymaps", () => {
    const extensions = setup({
      keymapConfig: { preset: "vim" },
    });
    const duplicates = getDuplicateKeymaps(
      EditorState.create({ extensions: extensions }),
    );
    // Total duplicates:
    // if this changes, please make sure to validate they are not conflicting
    expect(Object.values(duplicates).flat().length).toMatchInlineSnapshot(`19`);
    expect(duplicates).toMatchSnapshot();
  });
});

test("placeholder adds another extension", () => {
  const withPlaceholder = setup({ showPlaceholder: true }).flat();
  const withoutPlaceholder = setup({ showPlaceholder: false }).flat();
  expect(withPlaceholder.length - 1).toBe(withoutPlaceholder.length);
});
