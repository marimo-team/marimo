/* Copyright 2026 Marimo. All rights reserved. */
import { EditorState } from "@codemirror/state";
import { afterEach, expect, it } from "vitest";
import { store } from "@/core/state/jotai";
import { searchState } from "../search-highlight";
import { findReplaceAtom } from "../state";

afterEach(() => {
  store.set(findReplaceAtom, { type: "setIsOpen", isOpen: false });
  store.set(findReplaceAtom, { type: "setFind", find: "" });
});

function searchOfNewEditor() {
  return EditorState.create({ extensions: [searchState] }).field(searchState)
    .spec.search;
}

it("seeds an editor built while the panel is open with the current search", () => {
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  store.set(findReplaceAtom, { type: "setIsOpen", isOpen: true });

  expect(searchOfNewEditor()).toBe("needle");
});

it("does not highlight a previous search in an editor built after the panel closed", () => {
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  store.set(findReplaceAtom, { type: "setIsOpen", isOpen: false });

  expect(searchOfNewEditor()).toBe("");
});
