/* Copyright 2024 Marimo. All rights reserved. */
import { SearchQuery } from "@codemirror/search";
import { RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  ViewPlugin,
  DecorationSet,
  EditorView,
  ViewUpdate,
} from "@codemirror/view";
import { QueryType, asQueryCreator } from "./query";
import { store } from "@/core/state/jotai";
import { findReplaceAtom } from "./state";
import { getAllEditorViews } from "@/core/cells/cells";

const setSearchQuery = StateEffect.define<SearchQuery>();

/**
 * Set the global search query to the current find/replace state.
 */
export function setGlobalSearchQuery() {
  const state = store.get(findReplaceAtom);
  const views = getAllEditorViews();
  for (const view of views) {
    if (view.state.readOnly) {
      continue;
    }
    view.dispatch({
      effects: setSearchQuery.of(
        new SearchQuery({
          search: state.findText,
          caseSensitive: state.caseSensitive,
          regexp: state.regexp,
          replace: state.replaceText,
          wholeWord: state.wholeWord,
        }),
      ),
    });
  }
}

/**
 * Clear the global search query.
 */
export function clearGlobalSearchQuery() {
  const views = getAllEditorViews();
  for (const view of views) {
    if (view.state.readOnly) {
      continue;
    }
    view.dispatch({
      effects: setSearchQuery.of(new SearchQuery({ search: "" })),
    });
  }
}

export const searchState: StateField<QueryType> = StateField.define<QueryType>({
  create() {
    const state = store.get(findReplaceAtom);
    const search = new SearchQuery({
      search: state.findText,
      caseSensitive: state.caseSensitive,
      regexp: state.regexp,
      replace: state.replaceText,
      wholeWord: state.wholeWord,
    });

    return asQueryCreator(search).create();
  },
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setSearchQuery)) {
        value = asQueryCreator(effect.value).create();
      }
    }
    return value;
  },
});

const matchMark = Decoration.mark({
  class: "cm-searchMatch",
});
const selectedMatchMark = Decoration.mark({
  class: "cm-searchMatch cm-searchMatch-selected",
});

const HighlightMargin = 250;

// Adapted from from https://github.com/codemirror/search/blob/e766a897aef7515f7ded46ee60b60b875241239e/src/search.ts

export const searchHighlighter = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(readonly view: EditorView) {
      this.decorations = this.highlight(view.state.field(searchState));
    }

    update(update: ViewUpdate) {
      const state = update.state.field(searchState);
      if (
        state != update.startState.field(searchState) ||
        update.docChanged ||
        update.selectionSet ||
        update.viewportChanged
      ) {
        this.decorations = this.highlight(state);
      }
    }

    highlight(query: QueryType) {
      if (!query.spec.valid) {
        return Decoration.none;
      }
      const { view } = this;
      const builder = new RangeSetBuilder<Decoration>();
      const ranges = view.visibleRanges;
      const l = ranges.length;
      for (let i = 0; i < l; i++) {
        let { to } = ranges[i];
        const { from } = ranges[i];
        while (i < l - 1 && to > ranges[i + 1].from - 2 * HighlightMargin) {
          to = ranges[++i].to;
        }
        query.highlight(view.state, from, to, (from, to) => {
          const selected = view.state.selection.ranges.some(
            (r) => r.from == from && r.to == to,
          );
          builder.add(from, to, selected ? selectedMatchMark : matchMark);
        });
      }
      return builder.finish();
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);

export const highlightTheme = EditorView.baseTheme({
  "&light .cm-searchMatch": { backgroundColor: "#99ff7780" },
  "&dark .cm-searchMatch": { backgroundColor: "#22bb0070" },

  "&light .cm-searchMatch-selected": { backgroundColor: "transparent" },
  "&dark .cm-searchMatch.cm-searchMatch-selected": {
    backgroundColor: "#6199ff88 !important",
  },
});
