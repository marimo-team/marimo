/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type AnalysisCells,
  setNotebookAnalysis,
} from "@/__tests__/notebook-analysis";
import { cellId, variableName } from "@/__tests__/branded";
import { languageAdapterState } from "@/core/codemirror/language/extension";
import { LanguageAdapters } from "@/core/codemirror/language/LanguageAdapters";
import type { ExperimentalFeatures } from "@/core/config/feature-flag";
import { getFeatureFlag } from "@/core/config/feature-flag";
import {
  type DataSourceConnection,
  dataSourceConnectionsAtom,
} from "@/core/datasets/data-source-connections";
import { type ConnectionName, DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { QualifiedColumn } from "@/core/datasets/types";
import type { DataTable } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { storageAtom } from "@/core/storage/state";
import type { StorageNamespace } from "@/core/storage/types";
import { openLensTarget } from "../actions";
import {
  CODE_LENS_HOVER_DELAY_MS,
  CODE_LENS_HOVER_GRACE_MS,
  codeLensBundle,
} from "../extension";
import { mountLensPopover } from "../popover";

vi.mock("@/core/config/feature-flag", () => ({
  getFeatureFlag: vi.fn(),
}));

vi.mock("../actions", () => ({
  openLensTarget: vi.fn(),
}));

vi.mock("../popover", () => ({
  mountLensPopover: vi.fn(() => vi.fn()),
}));

function mockFlags(flags: Partial<ExperimentalFeatures>) {
  vi.mocked(getFeatureFlag).mockImplementation((flag) => flags[flag] ?? false);
}

const DF_TABLE: DataTable = {
  name: "df",
  source: "memory",
  source_type: "local",
  num_rows: 1,
  num_columns: 1,
  columns: [],
  variable_name: variableName("df"),
};

const BUCKET_NAMESPACE: StorageNamespace = {
  name: variableName("bucket"),
  displayName: "bucket",
  protocol: "s3",
  rootPath: "s3://bucket",
  backendType: "obstore",
  storageEntries: [],
};

const ENGINE_CONNECTION: DataSourceConnection = {
  name: "engine" as ConnectionName,
  source: "postgres",
  dialect: "postgresql",
  display_name: "engine (postgres)",
  databases: [],
};

function seedStore(opts: {
  tables?: DataTable[];
  namespaces?: StorageNamespace[];
  connections?: DataSourceConnection[];
  cells?: AnalysisCells;
}) {
  store.set(datasetsAtom, {
    tables: opts.tables ?? [],
    expandedTables: new Set<string>(),
    expandedColumns: new Set<QualifiedColumn>(),
    columnsPreviews: new Map(),
  });
  store.set(storageAtom, {
    namespaces: opts.namespaces ?? [],
    entriesByPath: new Map(),
    pageMetadataByPath: new Map(),
  });
  store.set(dataSourceConnectionsAtom, {
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: new Map(
      (opts.connections ?? []).map((connection) => [
        connection.name,
        connection,
      ]),
    ),
  });
  setNotebookAnalysis(store, opts.cells ?? {});
}

describe("codeLensBundle", () => {
  let view: EditorView | null = null;

  beforeEach(() => {
    vi.useFakeTimers();
    mockFlags({ cache_panel: true });
    seedStore({});
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    document.body.innerHTML = "";
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  async function mount(
    code: string,
    language: "python" | "sql" | "markdown" = "python",
  ): Promise<EditorView> {
    const state = EditorState.create({
      doc: code,
      extensions: [
        python(),
        languageAdapterState.init(() => LanguageAdapters[language]),
        codeLensBundle(cellId("cell1")),
      ],
    });
    view = new EditorView({ state, parent: document.body });
    // Fire the debounced analysis, then flush the deferred dispatch
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    view.dispatch({});
    return view;
  }

  function lenses(v: EditorView): HTMLElement[] {
    return [...v.dom.querySelectorAll<HTMLElement>(".mo-code-lens")];
  }

  it("returns an empty extension when disabled via `display.code_lens`", () => {
    expect(codeLensBundle(cellId("cell1"), false)).toEqual([]);
  });

  it.each([false, true])(
    "skips unchanged lenses (with lens: %s)",
    async (withLens) => {
      seedStore({ tables: withLens ? [DF_TABLE] : [] });
      const v = await mount("df = load()");
      const dispatch = vi.spyOn(v, "dispatch");
      setNotebookAnalysis(store, {});
      vi.advanceTimersByTime(300);
      await Promise.resolve();
      expect(dispatch).not.toHaveBeenCalled();
    },
  );

  it("refreshes widget positions after edits and clears removed entities", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    v.dispatch({ changes: { from: 0, insert: "\n" } });
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    lenses(v)[0].dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);
    expect(mountLensPopover).toHaveBeenLastCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({ pos: 3 }),
    );
    seedStore({});
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    expect(lenses(v)).toEqual([]);
  });

  it("renders a lens at a dataframe declaration", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()\nx = 1");

    const found = lenses(v);
    expect(found).toHaveLength(1);
    expect(found[0].getAttribute("aria-label")).toBe("Open in data sources");
    // The native tooltip is replaced by the hover popover
    expect(found[0].getAttribute("title")).toBeNull();
  });

  it("opens the datasources panel on click", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");

    lenses(v)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));

    expect(openLensTarget).toHaveBeenCalledWith("table");
  });

  it("is keyboard focusable and activatable", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];

    expect(lens.getAttribute("role")).toBe("button");
    expect(lens.tabIndex).toBe(0);

    lens.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    expect(openLensTarget).toHaveBeenCalledWith("table");

    lens.dispatchEvent(
      new KeyboardEvent("keydown", { key: " ", bubbles: true }),
    );
    expect(openLensTarget).toHaveBeenCalledTimes(2);
  });

  it("renders a lens at a bucket declaration", async () => {
    seedStore({ namespaces: [BUCKET_NAMESPACE] });
    const v = await mount("bucket = get_bucket()");

    const found = lenses(v);
    expect(found).toHaveLength(1);
    expect(found[0].getAttribute("aria-label")).toBe("Open in remote storage");

    found[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(openLensTarget).toHaveBeenCalledWith("bucket");
  });

  it("renders a lens at a connection declaration", async () => {
    seedStore({ connections: [ENGINE_CONNECTION] });
    const v = await mount("engine = create_engine()");

    const found = lenses(v);
    expect(found).toHaveLength(1);
    expect(found[0].getAttribute("aria-label")).toBe("Open in data sources");

    found[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(openLensTarget).toHaveBeenCalledWith("connection");
  });

  it("renders a lens at mo.cache and mo.persistent_cache sites", async () => {
    const v = await mount(
      '@mo.cache\ndef f():\n    return 1\n\nwith mo.persistent_cache("k"):\n    pass',
    );

    const found = lenses(v);
    expect(found).toHaveLength(2);
    expect(found[0].getAttribute("aria-label")).toBe("Open cache panel");

    found[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(openLensTarget).toHaveBeenCalledWith("cache");
  });

  it("shows a popover on hover and hides it on leave", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];

    lens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);

    expect(v.dom.querySelector(".mo-cm-tooltip")).not.toBeNull();
    expect(mountLensPopover).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({ kind: "table", name: "df" }),
    );

    lens.dispatchEvent(new MouseEvent("mouseleave"));
    // Not hidden immediately: the pointer may be on its way into the popover
    expect(v.dom.querySelector(".mo-cm-tooltip")).not.toBeNull();
    vi.advanceTimersByTime(CODE_LENS_HOVER_GRACE_MS);
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBeNull();
  });

  it("stays open while the pointer is over the popover", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];

    lens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);
    const popover = v.dom.querySelector<HTMLElement>(".mo-cm-tooltip");
    expect(popover).not.toBeNull();

    // Icon -> popover within the grace period
    lens.dispatchEvent(new MouseEvent("mouseleave"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_GRACE_MS / 2);
    popover?.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_GRACE_MS * 5);
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBe(popover);

    // Popover -> icon: no re-show; the popover is kept as-is
    popover?.dispatchEvent(new MouseEvent("mouseleave"));
    lens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS * 2);
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBe(popover);
    expect(mountLensPopover).toHaveBeenCalledTimes(1);

    // Leaving the popover for good hides it after the grace period
    lens.dispatchEvent(new MouseEvent("mouseleave"));
    popover?.dispatchEvent(new MouseEvent("mouseenter"));
    popover?.dispatchEvent(new MouseEvent("mouseleave"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_GRACE_MS);
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBeNull();
  });

  it("keeps the popover open across a lens rebuild for the same lens", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];

    lens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);
    const popover = v.dom.querySelector(".mo-cm-tooltip");
    expect(popover).not.toBeNull();

    // A store update triggers a (debounced) recompute of the same lenses
    seedStore({ tables: [DF_TABLE] });
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    v.dispatch({});
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBe(popover);

    // ...but a rebuild that drops the hovered lens closes it
    seedStore({ tables: [] });
    vi.advanceTimersByTime(300);
    await Promise.resolve();
    v.dispatch({});
    expect(lenses(v)).toHaveLength(0);
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBeNull();
  });

  it("dismisses the editor's own hover tooltips when the icon is entered", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];
    // CodeMirror's `hoverTooltip` listens for `mouseleave` on `view.dom` to
    // cancel a pending hover and close an open one
    const onLeave = vi.fn();
    v.dom.addEventListener("mouseleave", onLeave);

    lens.dispatchEvent(new MouseEvent("mouseenter"));

    expect(onLeave).toHaveBeenCalledTimes(1);
    expect(onLeave.mock.calls[0][0].relatedTarget).toBe(lens);
  });

  it("does not show a popover before the hover delay", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()");
    const lens = lenses(v)[0];

    lens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS - 100);
    lens.dispatchEvent(new MouseEvent("mouseleave"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);

    expect(v.dom.querySelector(".mo-cm-tooltip")).toBeNull();
  });

  it("passes cache context to the popover", async () => {
    const v = await mount(
      '@mo.cache\ndef add(a, b):\n    return a + b\n\nwith mo.persistent_cache("k"):\n    pass',
    );
    const [decoratorLens, withLens] = lenses(v);

    decoratorLens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);
    expect(mountLensPopover).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        kind: "cache",
        cache: { boundName: "add", cacheName: null },
      }),
    );

    decoratorLens.dispatchEvent(new MouseEvent("mouseleave"));
    withLens.dispatchEvent(new MouseEvent("mouseenter"));
    vi.advanceTimersByTime(CODE_LENS_HOVER_DELAY_MS);
    expect(mountLensPopover).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        kind: "cache",
        cache: { boundName: null, cacheName: "k" },
      }),
    );
  });

  it.each(["sql", "markdown"] as const)(
    "does not render lenses in %s cells",
    async (language) => {
      // A `mo.cache` inside a SQL string (or markdown) must not get an icon.
      seedStore({ tables: [DF_TABLE] });
      const v = await mount("df = load()\nmo.cache(f)", language);

      expect(lenses(v)).toHaveLength(0);
    },
  );

  it("does not render cache lenses when the cache panel is disabled", async () => {
    mockFlags({ cache_panel: false });
    const v = await mount("@mo.cache\ndef f():\n    return 1");

    expect(lenses(v)).toHaveLength(0);
  });

  it("only decorates the declaring cell", async () => {
    seedStore({
      tables: [DF_TABLE],
      cells: { "other-cell": { defs: ["df"] }, cell1: { refs: ["df"] } },
    });
    const v = await mount("df = load()");

    expect(lenses(v)).toHaveLength(0);
  });

  it("decorates only the declaration site, not later references", async () => {
    seedStore({ tables: [DF_TABLE] });
    const v = await mount("df = load()\ndf.head()");

    expect(lenses(v)).toHaveLength(1);
  });
});
