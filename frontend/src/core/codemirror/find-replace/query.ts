/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import { SearchCursor, SearchQuery } from "@codemirror/search";
import { EditorState } from "@codemirror/state";

type SearchResult = typeof SearchCursor.prototype.value;

// Copied from https://github.com/codemirror/search/blob/6.5.2/src/search.ts#L164
export interface QueryType<Result extends SearchResult = SearchResult> {
  nextMatch(state: EditorState, curFrom: number, curTo: number): Result | null;
  prevMatch(state: EditorState, curFrom: number, curTo: number): Result | null;
  getReplacement(result: Result): string;
  matchAll(state: EditorState, limit: number): readonly Result[] | null;
  highlight(
    state: EditorState,
    from: number,
    to: number,
    add: (from: number, to: number) => void,
  ): void;
  spec: SearchQuery;
}

export interface QueryCreator {
  create(): QueryType;
}

export function asQueryCreator(query: SearchQuery): QueryCreator {
  invariant("create" in query, 'Expected query to have a "create" method');
  return query as unknown as QueryCreator;
}
