/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion, CompletionSource } from "@codemirror/autocomplete";
import {
  keywordCompletionSource,
  schemaCompletionSource,
} from "@codemirror/lang-sql";
import type { EditorState } from "@codemirror/state";
import { DefaultSqlTooltipRenders } from "@marimo-team/codemirror-sql";
import { escapeSQLString } from "@marimo-team/smart-cells";
import { once } from "@/utils/once";
import { languageMetadataField } from "../../metadata";
import { SQL_IDENTIFIER } from "./completion-builder";
import { sqlCompletionContext } from "./completion-context";
import { SCHEMA_CACHE } from "./completion-store";
import type { SQLLanguageAdapterMetadata } from "./sql";

const IDENTIFIER_QUOTES = new Set(['"', "`", "["]);
const BARE_IDENTIFIER = /^[a-zA-Z_][\w$]*$/;

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

export function literalSQLCompletions(
  source: CompletionSource,
  kind: "schema" | "query" = "schema",
): CompletionSource {
  return async (ctx) => {
    const metadata = getSQLMetadata(ctx.state);
    const fString = metadata.quotePrefix.includes("f");
    const {
      context,
      toSource,
      literalPrefix,
      encodeQuery,
      displayQuery,
      isQuotedQuery,
      insideOpaque,
    } = sqlCompletionContext(ctx, fString);
    if (insideOpaque) {
      return null;
    }
    const result = await source(context);
    if (!result) {
      return result;
    }

    const dialect = SCHEMA_CACHE.getDialect(metadata.engine);
    const typedQuote = context.state.sliceDoc(result.from, result.from + 1);
    const quoted = IDENTIFIER_QUOTES.has(typedQuote);
    const quote = quoted
      ? typedQuote
      : (dialect.spec.identifierQuotes?.[0] ?? '"');
    const closingQuote = quote === "[" ? "]" : quote;
    const prefix = quoted ? "" : literalPrefix(result.from);
    return {
      ...result,
      from: toSource(result.from),
      to: result.to === undefined ? undefined : toSource(result.to),
      options: result.options
        .map((option): Completion | null => {
          let text = option.apply ?? option.label;
          if (typeof text !== "string") {
            return null;
          }
          const metadataName =
            SQL_IDENTIFIER in option ? option[SQL_IDENTIFIER] : undefined;
          // lang-sql marks aliases taken from the query as constant completions.
          const fromQuery =
            typeof metadataName !== "string" &&
            (kind === "query" || option.type === "constant");
          if (typeof metadataName === "string") {
            text =
              quoted || !BARE_IDENTIFIER.test(metadataName)
                ? quote +
                  metadataName.replaceAll(
                    closingQuote,
                    closingQuote.repeat(2),
                  ) +
                  closingQuote
                : metadataName;
          }
          const displayLabel = fromQuery
            ? displayQuery(option.label)
            : option.label;
          const label = fromQuery
            ? encodeQuery(option.label)
            : prefix + escapeSQLString(option.label, fString);
          if (
            fromQuery &&
            (!BARE_IDENTIFIER.test(text) || isQuotedQuery(text)) &&
            !text.startsWith(quote)
          ) {
            text = quote + text + closingQuote;
          }
          const apply = fromQuery
            ? encodeQuery(text)
            : prefix + escapeSQLString(text, fString);
          if (
            !fromQuery &&
            apply === (option.apply ?? option.label) &&
            label === option.label
          ) {
            return option;
          }
          return {
            ...option,
            label,
            displayLabel:
              label === displayLabel ? option.displayLabel : displayLabel,
            apply,
            detail:
              fromQuery && option.detail
                ? displayQuery(option.detail)
                : option.detail,
            info:
              fromQuery && typeof option.info === "string"
                ? displayQuery(option.info)
                : option.info,
          };
        })
        .filter((option) => option !== null),
    };
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
  const keywords =
    await import("@marimo-team/codemirror-sql/data/common-keywords.json");
  // Include DuckDB for now, but we can remove this once we have a better way to handle dialect-specific keywords
  const duckdbKeywords =
    await import("@marimo-team/codemirror-sql/data/duckdb-keywords.json");
  return {
    ...keywords.default.keywords,
    ...duckdbKeywords.default.keywords,
  };
});
