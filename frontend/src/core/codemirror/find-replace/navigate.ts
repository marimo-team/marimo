/* Copyright 2026 Marimo. All rights reserved. */

import { SearchQuery } from "@codemirror/search";
import { EditorSelection } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { getCellDocuments, writeCellCode } from "../cell-documents";
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
  const documents = getCellDocuments();
  const current = store.get(findReplaceAtom).currentView;
  const startingCellId = current?.cellId ?? documents[0]?.cellId;
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
    documents.findIndex((doc) => doc.cellId === startingCellId),
  );
  for (const document of [...documents, ...documents].slice(start)) {
    const { state } = document;
    const match =
      direction === "next"
        ? query.nextMatch(state, 0, position ?? 0)
        : query.prevMatch(
            state,
            position ?? state.doc.length,
            state.doc.length,
          );
    const view = match ? document.ensureView() : undefined;
    if (match && view) {
      return { view, match };
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
  const undoHandlers: (() => void)[] = [];
  for (const document of getCellDocuments()) {
    const { state } = document;
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

    const { cellId, code: previousCode } = document;
    undoHandlers.push(() => {
      writeCellCode(cellId, previousCode, { userEvent: "input.replace.all" });
    });
    document.applyChanges(changes, "input.replace.all");
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
  let count = 0;

  // Position in the document, keyed by cell and then by to:from
  const position = new Map<CellId, Map<string, number>>();
  for (const { cellId, state } of getCellDocuments()) {
    const matches = query.matchAll(state, 1e9) || [];
    for (const match of matches) {
      const { from, to } = match;
      const cellPosition = position.get(cellId) || new Map<string, number>();
      cellPosition.set(`${from}:${to}`, count++);
      position.set(cellId, cellPosition);
    }
  }

  return {
    count: count,
    position: position,
  };
});
