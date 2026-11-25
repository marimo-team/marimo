/* Copyright 2026 Marimo. All rights reserved. */

import { SearchQuery } from "@codemirror/search";
import { EditorSelection } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { getSearchDocuments } from "./documents";
import type { CellId } from "@/core/cells/ids";
import { replaceEditorContent } from "@/core/codemirror/replace-editor-content";
import { store } from "@/core/state/jotai";
import { scrollOwnerCell } from "../utils";
import { asQueryCreator, type QueryType } from "./query";
import { findReplaceAtom } from "./state";

function searchCommand<T>(
  f: (state: { query: QueryType; search: SearchQuery }) => T,
) {
  return () => {
    const state = store.get(findReplaceAtom);
    const search = new SearchQuery({
      search: state.findText,
      caseSensitive: state.caseSensitive,
      regexp: state.regexp,
      replace: state.replaceText,
      wholeWord: state.wholeWord,
    });
    return search.valid
      ? f({ query: asQueryCreator(search).create(), search })
      : false;
  };
}

/** Search document text first; construct only the matching cell's editor. */
function findMatch(
  query: QueryType,
  direction: "next" | "prev",
  includeCurrent = false,
) {
  const documents = getSearchDocuments();
  const current = store.get(findReplaceAtom).currentView;
  const startingKey = current?.view ?? documents[0]?.key;
  let position: number | undefined = current
    ? direction === "prev" || includeCurrent
      ? current.range.from
      : current.range.to
    : 0;
  if (direction === "prev") {
    documents.reverse();
  }
  const start = Math.max(
    0,
    documents.findIndex((doc) => doc.key === startingKey),
  );
  const ordered = [...documents, ...documents].slice(start);
  for (const document of ordered) {
    const { state } = document;
    const match =
      direction === "next"
        ? query.nextMatch(state, 0, position ?? 0)
        : query.prevMatch(
            state,
            position ?? state.doc.length,
            state.doc.length,
          );
    if (match) {
      const view = document.ensureView();
      return view ? { view, match } : undefined;
    }
    position = undefined;
    document.view?.dispatch({ selection: EditorSelection.single(0) });
  }
}

const findInDirection = (direction: "next" | "prev") =>
  searchCommand(({ query }) => {
    const found = findMatch(query, direction);
    if (!found) {
      return false;
    }
    const { view, match } = found;
    const selection = EditorSelection.single(match.from, match.to);
    view.dispatch({
      selection,
      effects: [EditorView.scrollIntoView(selection.main, { y: "center" })],
      userEvent: "select.search",
    });
    scrollOwnerCell(view);
    store.set(findReplaceAtom, {
      type: "setCurrentView",
      view,
      range: { from: match.from, to: match.to },
    });
    return match;
  });

/**
 * Find the next match after the global selection.
 */
export const findNext = findInDirection("next");
/**
 * Find the previous match before the global selection.
 */
export const findPrev = findInDirection("prev");

/**
 * Replace the next match after the global selection.
 */
export const replaceAll = searchCommand(({ query }) => {
  const views = getSearchDocuments();
  const undoHandlers: (() => void)[] = [];
  for (const document of views) {
    const { state, view } = document;
    if (state.readOnly) {
      continue;
    }

    const changes = query.matchAll(state, 1e9)?.map((match) => {
      const { from, to } = match;
      return { from, to, insert: query.getReplacement(match) };
    });

    if (!changes || changes.length === 0) {
      continue;
    }

    const prevDoc = state.doc.toString();
    if (!view) {
      document.replaceText(state.update({ changes }).state.doc.toString());
      undoHandlers.push(() => document.replaceText(prevDoc));
      continue;
    }
    undoHandlers.push(() => {
      replaceEditorContent(view, prevDoc, {
        userEvent: "input.replace.all",
      });
    });

    view.dispatch({
      changes,
      userEvent: "input.replace.all",
    });
  }

  const handleUndo = () => {
    for (const undoHandler of undoHandlers) {
      undoHandler();
    }
  };

  return handleUndo;
});

/**
 * Replace the next match after the global selection.
 */
export const replaceNext = searchCommand(({ query }) => {
  const found = findMatch(query, "next", true);
  if (!found) {
    return false;
  }
  const { view, match } = found;
  view.dispatch({
    changes: [
      {
        from: match.from,
        to: match.to,
        insert: view.state.toText(query.getReplacement(match)),
      },
    ],
    userEvent: "input.replace",
  });
  return findNext();
});

/**
 * @returns The number of matches in the document for each view.
 */
export const getMatches = searchCommand(({ query }) => {
  const views = getSearchDocuments();
  let count = 0;

  // Position in the document, keyed by view and then by to:from
  const position = new Map<EditorView | CellId, Map<string, number>>();
  for (const document of views) {
    const { state } = document;
    const matches = query.matchAll(state, 1e9) || [];
    for (const match of matches) {
      const { from, to } = match;
      const viewPosition =
        position.get(document.key) || new Map<string, number>();
      viewPosition.set(`${from}:${to}`, count++);
      position.set(document.key, viewPosition);
    }
  }

  return {
    count: count,
    position: position,
  };
});
