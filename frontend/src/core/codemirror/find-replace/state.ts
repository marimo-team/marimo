/* Copyright 2024 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { EditorView } from "@codemirror/view";
import { atomWithReducer } from "jotai/utils";

interface FindReplaceState {
  findText: string;
  replaceText: string;
  caseSensitive: boolean;
  wholeWord: boolean;
  regexp: boolean;
  isOpen: boolean;
  currentView?: {
    view: EditorView;
    range: { from: number; to: number };
  };
}

type Action =
  | {
      type: "setFind";
      find: string;
    }
  | {
      type: "setReplace";
      replace: string;
    }
  | {
      type: "setCaseSensitive";
      caseSensitive: boolean;
    }
  | {
      type: "setWholeWord";
      wholeWord: boolean;
    }
  | {
      type: "setRegex";
      regexp: boolean;
    }
  | {
      type: "setIsOpen";
      isOpen: boolean;
    }
  | {
      type: "setCurrentView";
      view: EditorView;
      range: { from: number; to: number };
    }
  | {
      type: "clearCurrentView";
    };

export const findReplaceAtom = atomWithReducer<FindReplaceState, Action>(
  {
    findText: "",
    replaceText: "",
    caseSensitive: false,
    wholeWord: false,
    regexp: false,
    isOpen: false,
    currentView: undefined,
  },
  (state, action) => {
    if (action === undefined) {
      return state;
    }

    switch (action.type) {
      case "setFind":
        return { ...state, findText: action.find };
      case "setReplace":
        return { ...state, replaceText: action.replace };
      case "setCaseSensitive":
        return { ...state, caseSensitive: action.caseSensitive };
      case "setWholeWord":
        return { ...state, wholeWord: action.wholeWord };
      case "setRegex":
        return { ...state, regexp: action.regexp };
      case "setIsOpen":
        return { ...state, isOpen: action.isOpen };
      case "setCurrentView":
        return {
          ...state,
          currentView: { view: action.view, range: action.range },
        };
      case "clearCurrentView":
        return { ...state, currentView: undefined };
    }
  },
);

export function openFindReplacePanel(initialView?: EditorView): boolean {
  // If any radix dialog is open, don't open the find/replace panel
  // they have role="dialog" and data-state="open"
  const element = document.querySelector('[role="dialog"][data-state="open"]');
  if (element) {
    return false;
  }

  if (initialView) {
    // Set the selected text and focus
    const selection = initialView.state.selection.main;
    const query = initialView.state.sliceDoc(selection.from, selection.to);
    if (query) {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: query,
      });
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: initialView,
        range: { from: selection.from, to: selection.to },
      });
    } else {
      // If there is no selection, just set the current view
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: initialView,
        range: { from: 0, to: 0 },
      });
    }
  }

  // HACK: If open, close it and re-open it to gain focus
  const isOpen = store.get(findReplaceAtom).isOpen;
  if (isOpen) {
    store.set(findReplaceAtom, {
      type: "setIsOpen",
      isOpen: false,
    });
    requestAnimationFrame(() => {
      // Open the panel
      store.set(findReplaceAtom, {
        type: "setIsOpen",
        isOpen: true,
      });
    });
    return true;
  }

  // Open the panel
  store.set(findReplaceAtom, {
    type: "setIsOpen",
    isOpen: true,
  });
  return true;
}

export function closeFindReplacePanel(): boolean {
  const isOpen = store.get(findReplaceAtom).isOpen;
  // If the panel is already closed, return false.
  if (!isOpen) {
    return false;
  }

  store.set(findReplaceAtom, {
    type: "setIsOpen",
    isOpen: false,
  });
  return true;
}
