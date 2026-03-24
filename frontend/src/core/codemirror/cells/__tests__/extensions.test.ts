/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  EditorState,
  Transaction,
  type TransactionSpec,
} from "@codemirror/state";
import { describe, expect, it } from "vitest";
import { formattingChangeEffect } from "../../format";
import { loroSyncAnnotation } from "../../rtc/loro/sync";
import { exportedForTesting } from "../extensions";

const { shouldAutorunMarkdownUpdate } = exportedForTesting;

function createTransaction(spec: TransactionSpec) {
  return EditorState.create({ doc: "" }).update(spec);
}

describe("shouldAutorunMarkdownUpdate", () => {
  it.each([
    "input.type",
    "delete.backward",
    "undo",
    "redo",
  ])("accepts local %s transactions", (userEvent) => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.userEvent.of(userEvent)],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
      }),
    ).toBe(true);
  });

  it("ignores formatting changes", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.userEvent.of("input.type")],
      effects: [formattingChangeEffect.of(true)],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
      }),
    ).toBe(false);
  });

  it("ignores RTC sync transactions", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [
        Transaction.userEvent.of("input.type"),
        loroSyncAnnotation.of(true),
      ],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        hasFocus: true,
      }),
    ).toBe(false);
  });

  it("ignores programmatic doc changes without a user event", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
      }),
    ).toBe(false);
  });

  it("allows focused local doc changes without user event annotations", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        hasFocus: true,
      }),
    ).toBe(true);
  });

  it("honors the predicate gate", () => {
    const transaction = createTransaction({
      changes: { from: 0, insert: "#" },
      annotations: [Transaction.userEvent.of("input.type")],
    });

    expect(
      shouldAutorunMarkdownUpdate({
        docChanged: transaction.docChanged,
        transactions: [transaction],
        predicate: () => false,
      }),
    ).toBe(false);
  });
});
