/* Copyright 2026 Marimo. All rights reserved. */

import {
  type Completion,
  type CompletionSource,
  acceptCompletion,
  autocompletion,
  CompletionContext,
  currentCompletions,
  startCompletion,
  setSelectedCompletion,
} from "@codemirror/autocomplete";
import { PostgreSQL, schemaCompletionSource, sql } from "@codemirror/lang-sql";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { parser as pythonParser } from "@lezer/python";
import {
  aliasColumnCompletionSource,
  createCteCompletionSource,
} from "@marimo-team/codemirror-sql";
import { escapeSQLString, SQLParser } from "@marimo-team/smart-cells";
import { waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DataTable } from "@/core/kernel/messages";
import { CompletionBuilder } from "../languages/sql/completion-builder";
import { literalSQLCompletions } from "../languages/sql/completion-sources";
import { languageMetadataField } from "../metadata";

const parser = new SQLParser();
const table = (name: string, column = "id"): DataTable => ({
  name,
  source: "test",
  source_type: "connection",
  type: "table",
  num_columns: 1,
  num_rows: 0,
  variable_name: null,
  columns: [
    { name: column, type: "string", external_type: "TEXT", sample_values: [] },
  ],
});

function completionSource(
  name: string,
  column = "id",
  schema = "public",
  database = "db",
) {
  const builder = new CompletionBuilder()
    .addDatabase([database], {
      name: database,
      dialect: "postgres",
      schemas: [],
    })
    .addSchema([database, schema], { name: schema, tables: [] })
    .addTable([database, schema], table(name, column));
  return literalSQLCompletions(
    schemaCompletionSource({
      dialect: PostgreSQL,
      schema: builder.build(),
      defaultSchema: `${database}.${schema}`,
    }),
  );
}

function state(doc: string, fString = true) {
  return EditorState.create({
    doc,
    extensions: [
      sql({ dialect: PostgreSQL }),
      languageMetadataField.init(() => ({
        ...parser.defaultMetadata,
        quotePrefix: fString ? "f" : "",
      })),
    ],
  });
}

function completionLabel(option: Completion): string {
  return option.displayLabel ?? option.label;
}

async function acceptAtEnd({
  doc,
  source,
  label,
}: {
  doc: string;
  source: CompletionSource;
  label: string;
}): Promise<string> {
  const view = new EditorView({
    parent: document.body,
    state: EditorState.create({
      doc,
      selection: { anchor: doc.length },
      extensions: [
        sql({ dialect: PostgreSQL }),
        languageMetadataField.init(() => parser.defaultMetadata),
        autocompletion({ override: [source], interactionDelay: 0 }),
      ],
    }),
  });
  try {
    startCompletion(view);
    await waitFor(() =>
      expect(currentCompletions(view.state).map(completionLabel)).toContain(
        label,
      ),
    );
    const index = currentCompletions(view.state).findIndex(
      (option) => completionLabel(option) === label,
    );
    view.dispatch({ effects: setSelectedCompletion(index) });
    expect(acceptCompletion(view)).toBe(true);
    return view.state.doc.toString();
  } finally {
    view.destroy();
  }
}

function assertLiteral(code: string) {
  const syntax = pythonParser.parse(code).toString();
  expect(syntax).not.toContain("⚠");
  expect(syntax).not.toContain("FormatReplacement");
  expect(syntax).not.toContain("BinaryExpression");
  expect(code.match(/mo.sql/g)).toHaveLength(1);
}

const names = [
  "t{1+1}",
  String.raw`t\""" + str(1+1) + "a"""""`,
  't"""""""',
  String.raw`t\path\n`,
  't"quoted"',
  "t雪😀",
  "t\nline\rreturn",
];

describe("literal SQL completions", () => {
  it.each(names)(
    "preserves %j through completion and Python/SQL round trips",
    async (name) => {
      const doc = 'SELECT * FROM "db"."public"."t"';
      const position = doc.length - 1;
      const result = await completionSource(name)(
        new CompletionContext(state(doc), position, true),
      );
      const option = result?.options.find((option) =>
        completionLabel(option).includes(name),
      );
      expect(option).toBeDefined();
      const apply = option?.apply ?? option?.label;
      expect(typeof apply).toBe("string");
      if (!result || typeof apply !== "string") {
        throw new Error("Missing string completion");
      }
      const query =
        doc.slice(0, result.from) + apply + doc.slice(result.to ?? position);
      const output = parser.transformOut(query, parser.defaultMetadata).code;
      assertLiteral(output);
      const roundTrip = parser.transformIn(output);
      expect(roundTrip.code).toBe(query);
      expect(parser.transformOut(roundTrip.code, roundTrip.metadata).code).toBe(
        output,
      );
      expect(query).toBe(
        `SELECT * FROM "db"."public".${escapeSQLString(`"${name.replaceAll('"', '""')}"`)}`,
      );
    },
  );

  it.each([true, false])(
    "resolves qualified metadata without changing labels (f=%j)",
    async (fString) => {
      const source = completionSource("t{x}", "c{y}", "s{z}", "d{w}");
      const encode = (name: string) => escapeSQLString(name, fString);
      for (const [doc, label] of [
        ["SELECT * FROM d", "d{w}"],
        [`SELECT * FROM "${encode("d{w}")}".s`, "s{z}"],
        [`SELECT * FROM "${encode("d{w}")}"."${encode("s{z}")}".t`, "t{x}"],
        [
          `SELECT "${encode("d{w}")}"."${encode("s{z}")}"."${encode("t{x}")}".c`,
          "c{y}",
        ],
      ]) {
        const result = await source(
          new CompletionContext(state(doc, fString), doc.length, true),
        );
        expect(
          result?.options.find((o) => completionLabel(o) === label)?.apply,
        ).toBe(encode(`"${label}"`));
      }
    },
  );

  it.each(["a{{b}}", "a{variable}"])(
    "preserves query-derived alias %s",
    async (alias) => {
      const doc = `SELECT * FROM t AS "${alias}" WHERE a`;
      const result = await completionSource("t")(
        new CompletionContext(state(doc), doc.length, true),
      );
      const option = result?.options.find(
        (o) =>
          completionLabel(o) ===
          alias.replaceAll("{{", "{").replaceAll("}}", "}"),
      );
      expect(option?.apply ?? option?.label).toBe(`"${alias}"`);
    },
  );

  it("keeps interpolated aliases unquoted when their definition is unquoted", async () => {
    const doc = "SELECT * FROM t AS a{variable} WHERE a";
    const result = await completionSource("t")(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(result?.options.find((o) => o.type === "constant")?.apply).toBe(
      "a{variable}",
    );
  });

  it("keeps interpolated CTEs unquoted when their definition is unquoted", async () => {
    const doc = "WITH q{variable} AS (SELECT 1 AS id) SELECT * FROM q";
    const source = literalSQLCompletions(createCteCompletionSource(), "query");
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(
      result?.options.find((o) => completionLabel(o) === "q{variable}")?.apply,
    ).toBe("q{variable}");
  });

  it.each(["a{env}", "a{env}S"])(
    "accepts an interpolated alias after %s without duplicating its prefix",
    async (prefix) => {
      const source = literalSQLCompletions(
        schemaCompletionSource({
          dialect: PostgreSQL,
          schema: new CompletionBuilder()
            .addTable([], table("reports"))
            .build(),
        }),
      );
      const result = await acceptAtEnd({
        doc: `SELECT * FROM reports AS a{env}Suffix WHERE ${prefix}`,
        source,
        label: "a{env}Suffix",
      });
      expect(result).toBe(
        "SELECT * FROM reports AS a{env}Suffix WHERE a{env}Suffix",
      );
    },
  );

  it.each(["q{env}", "q{env}S"])(
    "accepts an interpolated CTE after %s without duplicating its prefix",
    async (prefix) => {
      const result = await acceptAtEnd({
        doc: `WITH q{env}Suffix AS (SELECT 1 AS id) SELECT * FROM ${prefix}`,
        source: literalSQLCompletions(createCteCompletionSource(), "query"),
        label: "q{env}Suffix",
      });
      expect(result).toBe(
        "WITH q{env}Suffix AS (SELECT 1 AS id) SELECT * FROM q{env}Suffix",
      );
    },
  );

  it("preserves quoted CTE fields beyond the initial SQL parse viewport", async () => {
    const doc = `${"-- earlier statements\n".repeat(400)}WITH "q{variable}" AS (SELECT 1 AS id) SELECT * FROM q`;
    const source = literalSQLCompletions(createCteCompletionSource(), "query");
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(
      result?.options.find((o) => completionLabel(o) === "q{variable}")?.apply,
    ).toBe('"q{variable}"');
  });

  it.each(["{value}us", "us{value}", "t_{env}"])(
    "preserves fields next to a metadata completion in %s",
    async (prefix) => {
      const doc = `SELECT * FROM ${prefix}`;
      const source = literalSQLCompletions(
        schemaCompletionSource({
          dialect: PostgreSQL,
          schema: new CompletionBuilder().addTable([], table("users")).build(),
        }),
      );
      const result = await source(
        new CompletionContext(state(doc), doc.length, true),
      );
      const option = result?.options.find(
        (o) => completionLabel(o) === "users",
      );
      if (!result || !option) {
        throw new Error("Missing metadata completion next to a field");
      }
      expect(result.from).toBe("SELECT * FROM ".length);
      const apply = option.apply ?? option.label;
      if (typeof apply !== "string") {
        throw new Error("Expected a literal insertion");
      }
      const query = `${doc.slice(0, result.from)}${apply}`;
      expect(query).toBe(`${doc.slice(0, doc.lastIndexOf("}") + 1)}users`);
      expect(
        pythonParser
          .parse(parser.transformOut(query, parser.defaultMetadata).code)
          .toString()
          .match(/FormatReplacement/g),
      ).toHaveLength(1);
    },
  );

  it("replaces the whole quoted identifier when its prefix contains a field", async () => {
    const doc = 'SELECT * FROM "{prefix}us"';
    const position = doc.length - 1;
    const source = literalSQLCompletions(
      schemaCompletionSource({
        dialect: PostgreSQL,
        schema: new CompletionBuilder().addTable([], table("users")).build(),
      }),
    );
    const result = await source(
      new CompletionContext(state(doc), position, true),
    );
    expect(result).toMatchObject({ from: doc.indexOf('"'), to: doc.length });
    const option = result?.options.find((o) => o.label === '"users"');
    expect(option?.apply ?? option?.label).toBe('"users"');
  });

  it("accepts a quoted completion in the mounted editor and preserves selection", async () => {
    const doc = 'SELECT * FROM "db"."public"."t" WHERE id = {value}';
    const position = doc.indexOf('"t"') + 2;
    const source = completionSource("t{1+1}");
    const view = new EditorView({
      parent: document.body,
      state: EditorState.create({
        doc,
        selection: { anchor: position },
        extensions: [
          sql({ dialect: PostgreSQL }),
          languageMetadataField.init(() => parser.defaultMetadata),
          autocompletion({ override: [source], interactionDelay: 0 }),
        ],
      }),
    });
    try {
      startCompletion(view);
      await waitFor(() =>
        expect(currentCompletions(view.state)).toHaveLength(1),
      );
      expect(completionLabel(currentCompletions(view.state)[0])).toBe(
        '"t{1+1}"',
      );
      view.dispatch({ effects: setSelectedCompletion(0) });
      expect(acceptCompletion(view)).toBe(true);
      expect(view.state.doc.toString()).toBe(
        'SELECT * FROM "db"."public"."t{{1+1}}" WHERE id = {value}',
      );
      expect(view.state.selection.main.anchor).toBe(position + 8);
    } finally {
      view.destroy();
    }
  });

  it.each([
    { name: "users", insertion: "users" },
    { name: "users{1+1}", insertion: '"users{{1+1}}"' },
  ])(
    "accepts $name next to a field without replacing the field or query suffix",
    async ({ name, insertion }) => {
      const doc = "SELECT * FROM {prefix}us WHERE id = {value}";
      const position = doc.indexOf(" WHERE");
      const source = literalSQLCompletions(
        schemaCompletionSource({
          dialect: PostgreSQL,
          schema: new CompletionBuilder().addTable([], table(name)).build(),
        }),
      );
      const view = new EditorView({
        parent: document.body,
        state: EditorState.create({
          doc,
          selection: { anchor: position },
          extensions: [
            sql({ dialect: PostgreSQL }),
            languageMetadataField.init(() => parser.defaultMetadata),
            autocompletion({ override: [source], interactionDelay: 0 }),
          ],
        }),
      });
      try {
        startCompletion(view);
        await waitFor(() =>
          expect(currentCompletions(view.state).map(completionLabel)).toContain(
            name,
          ),
        );
        expect(acceptCompletion(view)).toBe(true);
        const expected = `SELECT * FROM {prefix}${insertion} WHERE id = {value}`;
        expect(view.state.doc.toString()).toBe(expected);
        expect(view.state.selection.main.head).toBe(expected.indexOf(" WHERE"));
        expect(
          pythonParser
            .parse(parser.transformOut(expected, parser.defaultMetadata).code)
            .toString()
            .match(/FormatReplacement/g),
        ).toHaveLength(2);
      } finally {
        view.destroy();
      }
    },
  );

  it.each(["q{{x}}", "q{variable}", "q{variable}}}", String.raw`q\N{BULLET}`])(
    "preserves query-derived CTE %s",
    async (name) => {
      const source = literalSQLCompletions(
        createCteCompletionSource(),
        "query",
      );
      const doc = `WITH "${name}" AS (SELECT 1 AS id) SELECT * FROM q`;
      const result = await source(
        new CompletionContext(state(doc), doc.length, true),
      );
      const label = name.replaceAll("{{", "{").replaceAll("}}", "}");
      const option = result?.options.find((o) => completionLabel(o) === label);
      expect(option?.apply).toBe(`"${name}"`);
    },
  );

  it("completes metadata columns through a query alias", async () => {
    const schema = new CompletionBuilder()
      .addTable([], table("t{x}", "c{y}"))
      .build();
    const source = literalSQLCompletions(
      aliasColumnCompletionSource({ schema }),
      "query",
    );
    const doc = 'SELECT * FROM "t{{x}}" t WHERE t.c';
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(
      result?.options.find((o) => completionLabel(o) === "c{y}")?.apply,
    ).toBe('"c{{y}}"');
  });

  it("keeps alias fields distinct from identical literal table names", async () => {
    const doc = 'SELECT * FROM "a{{variable}}" AS "a{variable}" WHERE a';
    const result = await completionSource("a{variable}")(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(result?.options.find((o) => o.type === "constant")?.apply).toBe(
      '"a{variable}"',
    );
  });

  it("keeps CTE fields distinct from identical literal names in comments", async () => {
    const doc =
      '-- q{{variable}}\nWITH "q{variable}" AS (SELECT 1 AS id) SELECT * FROM q';
    const source = literalSQLCompletions(createCteCompletionSource(), "query");
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    expect(
      result?.options.find((o) => completionLabel(o) === "q{variable}")?.apply,
    ).toBe('"q{variable}"');
  });

  it("keeps metadata literal even when its name matches a field token", async () => {
    const name = "marimo_sql_field_0__";
    const doc = 'SELECT {value} FROM "db"."public".';
    const source = completionSource(name);
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    const option = result?.options.find((o) => completionLabel(o) === name);
    expect(option?.apply ?? option?.label).toBe(name);
  });

  it.each([
    'a{str("x\\n")}',
    "a{value:>{width}}",
    "a{{literal}}{value}",
    "a{value}}}",
    "a{value}{{",
    String.raw`a\N{BULLET}`,
  ])("preserves the exact fields in alias %s", async (alias) => {
    const doc = `SELECT * FROM t AS "${alias}" WHERE a`;
    const source = completionSource("t");
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    const option = result?.options.find((o) => o.type === "constant");
    expect(option?.apply).toBe(`"${alias}"`);
    expect(option?.label).not.toContain("marimo_sql_field_");
  });

  it("keeps a literal field-token spelling in a CTE name", async () => {
    const name = "marimo_sql_field_0__";
    const doc = `WITH "${name}" AS (SELECT {value} AS id) SELECT * FROM __marimo`;
    const source = literalSQLCompletions(createCteCompletionSource(), "query");
    const result = await source(
      new CompletionContext(state(doc), doc.length, true),
    );
    const option = result?.options.find((o) => completionLabel(o) === name);
    expect(option?.apply ?? option?.label).toBe(name);
  });

  it.each([
    { name: "t{1+1}", prefix: "t{{1" },
    { name: String.raw`a\b`, prefix: String.raw`a\\` },
  ])(
    "filters escaped source while displaying $name canonically",
    async ({ name, prefix }) => {
      const doc = `SELECT * FROM "db"."public"."${prefix}`;
      const view = new EditorView({
        parent: document.body,
        state: EditorState.create({
          doc,
          selection: { anchor: doc.length },
          extensions: [
            sql({ dialect: PostgreSQL }),
            languageMetadataField.init(() => parser.defaultMetadata),
            autocompletion({
              override: [completionSource(name)],
              interactionDelay: 0,
            }),
          ],
        }),
      });
      try {
        startCompletion(view);
        await waitFor(() =>
          expect(currentCompletions(view.state).map(completionLabel)).toContain(
            `"${name}"`,
          ),
        );
        await waitFor(() =>
          expect(
            view.dom.querySelector(".cm-tooltip-autocomplete")?.textContent,
          ).toContain(`"${name}"`),
        );
        const index = currentCompletions(view.state).findIndex(
          (o) => completionLabel(o) === `"${name}"`,
        );
        view.dispatch({ effects: setSelectedCompletion(index) });
        expect(acceptCompletion(view)).toBe(true);
        expect(view.state.doc.toString()).toBe(
          `SELECT * FROM "db"."public".${escapeSQLString(`"${name}"`)}`,
        );
      } finally {
        view.destroy();
      }
    },
  );

  it("does not offer metadata completions inside a Python field", async () => {
    const doc = "SELECT * FROM {table_name}";
    expect(
      await completionSource("table_name")(
        new CompletionContext(state(doc), doc.indexOf("}"), true),
      ),
    ).toBeNull();
  });

  it("drops function insertions that cannot be encoded as literal text", async () => {
    const doc = "SELECT * FROM t";
    const source = literalSQLCompletions(() => ({
      from: doc.length - 1,
      options: [
        {
          label: "table",
          apply: () => {
            throw new Error("Must not execute an unencoded insertion");
          },
        },
      ],
    }));
    expect(
      (await source(new CompletionContext(state(doc), doc.length, true)))
        ?.options,
    ).toEqual([]);
  });
});
