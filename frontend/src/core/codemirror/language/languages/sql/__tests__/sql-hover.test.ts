/* Copyright 2026 Marimo. All rights reserved. */

import {
  DefaultSqlTooltipRenders,
  type NamespaceTooltipData,
  sqlExtension,
} from "@marimo-team/codemirror-sql";
import { describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { PlaceholderType } from "@/core/codemirror/config/types";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { SQLLanguageAdapter } from "../sql";

vi.mock("@marimo-team/codemirror-sql", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("@marimo-team/codemirror-sql")>();
  return { ...original, sqlExtension: vi.fn(original.sqlExtension) };
});

const markup = "<b>x</b>";

// codemirror-sql uses the configured renderer for the semantic type, or the
// library default. Do the same, and then assign the result to innerHTML.
function renderHover(data: NamespaceTooltipData): HTMLElement {
  new SQLLanguageAdapter().getExtension({
    cellId: {} as CellId,
    completionConfig: {} as CompletionConfig,
    hotkeys: {} as HotkeyProvider,
    placeholderType: {} as PlaceholderType,
    lspConfig: {
      diagnostics: { sql_linter: true },
    } as LSPConfig & { diagnostics: DiagnosticsConfig },
  });
  const renderers =
    vi.mocked(sqlExtension).mock.lastCall?.[0]?.hoverConfig?.tooltipRenderers;
  const kind = data.item.semanticType;
  const render =
    kind === "table" || kind === "column"
      ? renderers?.[kind]
      : renderers?.namespace;
  const dom = document.createElement("div");
  dom.innerHTML = render
    ? render(data)
    : DefaultSqlTooltipRenders.namespace(data.item);
  return dom;
}

describe("SQL hover tooltips", () => {
  it("renders table column names as text", () => {
    const dom = renderHover({
      word: "users",
      resolvedSchema: {},
      item: {
        path: ["public", "users"],
        type: "namespace",
        semanticType: "table",
        completion: { label: "users" },
        namespace: [{ label: markup }, "id"],
      },
    });
    expect(dom.querySelector("b")).toBeNull();
    expect(dom.querySelector(".sql-hover-columns")?.textContent).toBe(
      `Columns (2):${markup}, id`,
    );
  });

  it("renders column names, details, and aliases as text", () => {
    const dom = renderHover({
      word: "u.col",
      aliasFor: "users",
      resolvedSchema: {},
      item: {
        path: ["users", markup],
        type: "completion",
        semanticType: "column",
        completion: { label: markup, detail: markup },
      },
    });
    expect(dom.querySelector("b")).toBeNull();
    expect(dom.querySelector(".sql-hover-alias")?.textContent).toBe(
      "u is an alias for users",
    );
    expect(dom.querySelector(".sql-hover-header strong")?.textContent).toBe(
      markup,
    );
    expect(dom.querySelector(".sql-hover-description")?.textContent).toBe(
      `Column: ${markup}`,
    );
  });

  it("renders schema paths as text", () => {
    const dom = renderHover({
      word: "main",
      resolvedSchema: {},
      item: {
        path: [markup, "main"],
        type: "namespace",
        semanticType: "schema",
        value: "main",
        namespace: { users: [] },
      },
    });
    expect(dom.querySelector("b")).toBeNull();
    expect(dom.querySelector(".sql-hover-path code")?.textContent).toBe(
      `${markup}.main`,
    );
    expect(dom.querySelector(".sql-hover-children")?.textContent).toBe(
      "Contains 1 table",
    );
  });
});
