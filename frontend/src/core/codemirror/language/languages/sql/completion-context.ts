/* Copyright 2026 Marimo. All rights reserved. */

import { CompletionContext } from "@codemirror/autocomplete";
import { ensureSyntaxTree, syntaxTree } from "@codemirror/language";
import type { ChangeDesc, EditorState } from "@codemirror/state";
import {
  escapeSQLString,
  getSQLInterpolationRanges,
} from "@marimo-team/smart-cells";

interface SQLField {
  source: string;
  from: number;
  to: number;
  quoted?: boolean;
}

interface SQLContext {
  state: EditorState;
  changes?: ChangeDesc;
  fields: ReadonlyMap<string, SQLField>;
  fieldPattern?: RegExp;
  opaqueRanges: ReadonlyArray<{ from: number; to: number }>;
  interpolations: ReadonlyArray<{ from: number; to: number }>;
}

const contexts = new WeakMap<EditorState, SQLContext>();
const escapes: Record<string, string> = {
  "\\": "\\",
  '"': '"',
  "'": "'",
  a: "\x07",
  b: "\b",
  f: "\f",
  n: "\n",
  r: "\r",
  t: "\t",
  v: "\v",
};

export function sqlCompletionContext(
  context: CompletionContext,
  fString: boolean,
) {
  let projected = contexts.get(context.state);
  if (!projected) {
    const source = context.state.doc.toString();
    const pattern =
      /\\(?:N\{[^}\r\n]+\}|[\\'"abfnrtv]|\r?\n|x[\da-fA-F]{2}|u[\da-fA-F]{4}|U[\da-fA-F]{8}|[0-7]{1,3})|\{\{|\}\}/g;
    const fields = fString ? getSQLInterpolationRanges(source) : [];
    const opaqueRanges = [...fields];
    const changes: Array<{ from: number; to: number; insert: string }> = [];
    const decodeLiteral = (from: number, to: number) => {
      for (const match of source.slice(from, to).matchAll(pattern)) {
        const start = from + match.index;
        const token = match[0];
        if (token.startsWith("\\N{")) {
          opaqueRanges.push({ from: start, to: start + token.length });
          continue;
        }
        let insert = token;
        if (token.startsWith("\\")) {
          const escaped = token.slice(1);
          if (escaped in escapes) {
            insert = escapes[escaped];
          } else if (/^[xuU]/.test(escaped)) {
            const codePoint = Number.parseInt(escaped.slice(1), 16);
            if (codePoint <= 0x10ffff) {
              insert = String.fromCodePoint(codePoint);
            }
          } else if (/^[0-7]/.test(escaped)) {
            insert = String.fromCodePoint(Number.parseInt(escaped, 8));
          } else {
            insert = "";
          }
        } else if (fString) {
          insert = token[0];
        }
        if (token !== insert) {
          changes.push({
            from: start,
            to: start + token.length,
            insert,
          });
        }
      }
    };
    let end = 0;
    for (const { from, to } of fields) {
      decodeLiteral(end, from);
      end = to;
    }
    decodeLiteral(end, source.length);
    opaqueRanges.sort((a, b) => a.from - b.from);
    // Field tokens preserve origin when an alias and a literal name look identical.
    const interpolations = new Map<string, SQLField>();
    let fieldPattern: RegExp | undefined;
    if (opaqueRanges.length > 0) {
      const decoded = context.state
        .changes(changes)
        .apply(context.state.doc)
        .toString();
      let prefix = "marimo_sql_field_";
      while (decoded.includes(prefix)) {
        prefix += "_";
      }
      fieldPattern = new RegExp(`${prefix}\\d+__`, "g");
      for (const [index, { from, to }] of opaqueRanges.entries()) {
        const token = `${prefix}${index}__`;
        interpolations.set(token, {
          source: source.slice(from, to),
          from,
          to,
        });
        changes.push({ from, to, insert: token });
      }
      changes.sort((a, b) => a.from - b.from);
    }
    if (changes.length === 0) {
      projected = {
        state: context.state,
        fields: interpolations,
        opaqueRanges,
        interpolations: fields,
      };
    } else {
      const transaction = context.state.update({ changes });
      projected = {
        state: transaction.state,
        changes: transaction.changes,
        fields: interpolations,
        fieldPattern,
        opaqueRanges,
        interpolations: fields,
      };
    }
    contexts.set(context.state, projected);
  }
  const restoreFields = (text: string): string =>
    projected.fieldPattern
      ? text.replaceAll(
          projected.fieldPattern,
          (token) => projected.fields.get(token)?.source ?? token,
        )
      : text;
  return {
    insideOpaque: projected.opaqueRanges.some(
      ({ from, to }) => from < context.pos && context.pos < to,
    ),
    isQuotedQuery: (text: string) => {
      if (!projected.fieldPattern) {
        return false;
      }
      for (const [token] of text.matchAll(projected.fieldPattern)) {
        const field = projected.fields.get(token);
        if (!field) {
          continue;
        }
        if (field.quoted === undefined) {
          const tree =
            ensureSyntaxTree(context.state, field.to, 20) ??
            syntaxTree(context.state);
          field.quoted =
            tree.resolveInner(field.from, 1).name === "QuotedIdentifier";
        }
        if (field.quoted) {
          return true;
        }
      }
      return false;
    },
    displayQuery: restoreFields,
    encodeQuery: (text: string) =>
      restoreFields(escapeSQLString(text, fString)),
    context: projected.changes
      ? new CompletionContext(
          projected.state,
          projected.changes.mapPos(context.pos),
          context.explicit,
          context.view,
        )
      : context,
    toSource: (position: number) =>
      projected.changes?.invertedDesc.mapPos(position) ?? position,
    toSourceStart: (position: number) => {
      let start = projected.changes?.invertedDesc.mapPos(position) ?? position;
      for (const { to } of projected.interpolations) {
        if (to <= context.pos) {
          start = Math.max(start, to);
        }
      }
      return start;
    },
  };
}
