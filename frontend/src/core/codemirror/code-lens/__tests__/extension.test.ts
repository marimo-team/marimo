/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
import { variablesAtom } from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import { openLensTarget } from "../actions";
import { CODE_LENS_HOVER_DELAY_MS, codeLensBundle } from "../extension";
import { mountLensPopover } from "../popover";

vi.mock("@/core/config/feature-flag", () => ({
  getFeatureFlag: vi.fn(),
}));

vi.mock("../actions", () => ({
  openLensTarget: vi.fn(),
}));

vi.mock("../popover", () => ({
  mountLensPopover: vi.fn(() => () => {}),
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
  variables?: Variables;
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
  store.set(variablesAtom, opts.variables ?? {});
}

describe("codeLensBundle", () => {
  let view: EditorView | null = null;

  beforeEach(() => {
    vi.useFakeTimers();
    mockFlags({ editor_code_lens: true, cache_panel: true });
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

  it("returns an empty extension when the flag is off", () => {
    mockFlags({ editor_code_lens: false });
    expect(codeLensBundle(cellId("cell1"))).toEqual([]);
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
    expect(v.dom.querySelector(".mo-cm-tooltip")).toBeNull();
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
    mockFlags({ editor_code_lens: true, cache_panel: false });
    const v = await mount("@mo.cache\ndef f():\n    return 1");

    expect(lenses(v)).toHaveLength(0);
  });

  it("only decorates the declaring cell", async () => {
    const dfName = variableName("df");
    seedStore({
      tables: [DF_TABLE],
      variables: {
        [dfName]: {
          name: dfName,
          declaredBy: [cellId("other-cell")],
          usedBy: [cellId("cell1")],
        },
      },
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
