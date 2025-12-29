/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion, CompletionSource } from "@codemirror/autocomplete";
import {
  keywordCompletionSource,
  schemaCompletionSource,
} from "@codemirror/lang-sql";
import type { EditorState } from "@codemirror/state";
import { DefaultSqlTooltipRenders } from "@marimo-team/codemirror-sql";
import { once } from "@/utils/once";
import { languageMetadataField } from "../../metadata";
import { SCHEMA_CACHE } from "./completion-store";
import type { SQLLanguageAdapterMetadata } from "./sql";

function getSQLMetadata(state: EditorState): SQLLanguageAdapterMetadata {
  return state.field(languageMetadataField) as SQLLanguageAdapterMetadata;
}

/**
 * Custom schema completion source that dynamically gets the Dialect and SQL tables.
 */
export function tablesCompletionSource(): CompletionSource {
  return (ctx) => {
    const metadata = getSQLMetadata(ctx.state);
    const connectionName = metadata.engine;
    const config = SCHEMA_CACHE.getCompletionSource(connectionName);

    if (!config) {
      return null;
    }

    const completions = schemaCompletionSource(config)(ctx);
    if (!completions) {
      return null;
    }

    return completions;
  };
}

/**
 * Custom keyword completion source that dynamically gets the Dialect.
 * This also ignores keyword completions on table columns.
 */
export function customKeywordCompletionSource(): CompletionSource {
  return (ctx) => {
    const metadata = getSQLMetadata(ctx.state);
    const connectionName = metadata.engine;
    const dialect = SCHEMA_CACHE.getDialect(connectionName);

    // We want to ignore keyword completions on something like
    // `WHERE my_table.col`
    //                    ^cursor
    const textBefore = ctx.matchBefore(/\.\w*/);
    if (textBefore) {
      // If there is a match, we are typing after a dot,
      // so we don't want to trigger SQL keyword completion
      return null;
    }

    const keywordRenderer = (label: string, type: string): Completion => {
      return {
        label,
        type,
        info: async () => {
          const keywordDocs = await getKeywordDocs();
          const keywordInfo = keywordDocs[label.toLocaleLowerCase()];
          if (!keywordInfo) {
            return null;
          }

          const dom = document.createElement("div");
          dom.innerHTML = DefaultSqlTooltipRenders.keyword({
            keyword: label,
            info: keywordInfo,
          });
          return dom;
        },
      };
    };

    const uppercaseKeywords = true;
    const result = keywordCompletionSource(
      dialect,
      uppercaseKeywords,
      keywordRenderer,
    )(ctx);
    return result;
  };
}

// e.g. lazily load keyword docs
const getKeywordDocs = once(async (): Promise<Record<string, unknown>> => {
  const keywords = await import(
    "@marimo-team/codemirror-sql/data/common-keywords.json"
  );
  // Include DuckDB for now, but we can remove this once we have a better way to handle dialect-specific keywords
  const duckdbKeywords = await import(
    "@marimo-team/codemirror-sql/data/duckdb-keywords.json"
  );
  return {
    ...keywords.default.keywords,
    ...duckdbKeywords.default.keywords,
  };
});
