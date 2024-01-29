/* Copyright 2024 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { SearchQuery } from "@codemirror/search";
import { EditorSelection } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { findReplaceAtom } from "./state";
import { getAllEditorViews } from "@/core/cells/cells";
import { QueryType, asQueryCreator } from "./query";

function searchCommand<T>(
  f: (state: { query: QueryType; search: SearchQuery }) => T
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

/**
 * Move the selection to the first match (next or previous) after the global selection.
 * Will wrap around to the start of the document when it reaches the end.
 *
 * This is a modified version of the original findNext/findPrev function,
 * that searches through all views, instead of just the current one.
 */
const findInDirection = (direction: "next" | "prev") =>
  searchCommand(({ query }) => {
    const views = getAllEditorViews();
    // Get starting view from the store
    const currentView = store.get(findReplaceAtom).currentView || {
      view: views[0],
      range: { from: 0, to: 0 },
    };

    let startingPosition: number | null = currentView.range.to;

    // We are going backwards so update the starting position and views to search
    if (direction === "prev") {
      views.reverse();
      startingPosition = currentView.range.from;
    }

    let startingViewIndex = views.indexOf(currentView.view);
    if (startingViewIndex < 0) {
      startingViewIndex = 0;
    }

    const viewsToSearch = [...views, ...views].slice(startingViewIndex);

    for (const view of viewsToSearch) {
      const next =
        direction === "next"
          ? query.nextMatch(view.state, 0, startingPosition ?? 0)
          : query.prevMatch(
              view.state,
              startingPosition ?? view.state.doc.length,
              view.state.doc.length
            );

      if (!next) {
        startingPosition = null; // Unset the starting position
        // If no match found in this view, continue to the next one
        // and remove the selection
        view.dispatch({
          selection: EditorSelection.single(0),
        });
        continue;
      }

      // Set selection
      const selection = EditorSelection.single(next.from, next.to);
      view.dispatch({
        selection,
        effects: [EditorView.scrollIntoView(selection.main, { y: "center" })],
        userEvent: "select.search",
      });
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view,
        range: { from: next.from, to: next.to },
      });

      return next; // If a match is found, stop searching and return true
    }

    return false; // If no matches are found in any view, return false
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
  const views = getAllEditorViews();
  const undoHandlers: Array<() => void> = [];
  for (const view of views) {
    if (view.state.readOnly) {
      continue;
    }

    const changes = query.matchAll(view.state, 1e9)?.map((match) => {
      const { from, to } = match;
      return { from, to, insert: query.getReplacement(match) };
    });

    if (!changes || changes.length === 0) {
      continue;
    }

    const prevDoc = view.state.doc.toString();
    undoHandlers.push(() => {
      view.dispatch({
        changes: [{ from: 0, to: view.state.doc.length, insert: prevDoc }],
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
  const views = getAllEditorViews();
  // Get starting view from the store
  const currentView = store.get(findReplaceAtom).currentView || {
    view: views[0],
    range: { from: 0, to: 0 },
  };

  // Start from the start of the selection to include the current match
  let startingPosition: number | null = currentView.range.from;

  let startingViewIndex = views.indexOf(currentView.view);
  if (startingViewIndex < 0) {
    startingViewIndex = 0;
  }
  const viewsToSearch = [...views, ...views].slice(startingViewIndex);

  for (const view of viewsToSearch) {
    const next = query.nextMatch(view.state, 0, startingPosition ?? 0);

    if (!next) {
      startingPosition = null; // Unset the starting position
      // If no match found in this view, continue to the next one
      // and remove the selection
      view.dispatch({
        selection: EditorSelection.single(0),
      });
      continue;
    }

    // Replace the match
    const replacement = view.state.toText(query.getReplacement(next));
    view.dispatch({
      changes: [{ from: next.from, to: next.to, insert: replacement }],
      userEvent: "input.replace",
    });

    // Find next match
    return findNext();
  }

  return false; // If no matches are found in any view, return false
});

/**
 * @returns The number of matches in the document for each view.
 */
export const getMatches = searchCommand(({ query }) => {
  const views = getAllEditorViews();
  let count = 0;

  // Position in the document, keyed by view and then by to:from
  const position = new Map<EditorView, Map<string, number>>();
  for (const view of views) {
    const matches = query.matchAll(view.state, 1e9) || [];
    for (const match of matches) {
      const { from, to } = match;
      const viewPosition = position.get(view) || new Map<string, number>();
      viewPosition.set(`${from}:${to}`, count++);
      position.set(view, viewPosition);
    }
  }

  return {
    count: count,
    position: position,
  };
});
