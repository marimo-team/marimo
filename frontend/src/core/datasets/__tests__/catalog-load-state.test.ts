/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { catalogPathKey, hydrateCatalogLoadState } from "../catalog-load-state";
import { makeSchema, makeTable } from "./catalog-fixtures";

describe("hydrateCatalogLoadState", () => {
  it("tracks sibling schemas under the same namespace with distinct table keys", () => {
    const catalogLoad = hydrateCatalogLoadState({
      databases: [
        {
          name: "catalog",
          dialect: "iceberg",
          children: [
            {
              kind: "namespace",
              name: "top",
              children: [
                makeSchema("first", [makeTable("table1")]),
                makeSchema("second", [makeTable("table2")]),
              ],
            },
          ],
        },
      ],
    });

    expect(
      catalogLoad.tablesLoaded.has(catalogPathKey("catalog", ["top", "first"])),
    ).toBe(true);
    expect(
      catalogLoad.tablesLoaded.has(
        catalogPathKey("catalog", ["top", "second"]),
      ),
    ).toBe(true);
    expect(
      catalogLoad.childrenLoaded.has(catalogPathKey("catalog", ["top"])),
    ).toBe(true);
    expect(
      catalogLoad.tablesLoaded.has(catalogPathKey("catalog", ["top"])),
    ).toBe(true);
  });

  it("does not mark deferred database roots with empty children", () => {
    const catalogLoad = hydrateCatalogLoadState({
      databases: [{ name: "catalog", dialect: "iceberg", children: [] }],
    });

    expect(catalogLoad.childrenLoaded.has(catalogPathKey("catalog", []))).toBe(
      false,
    );
    expect(catalogLoad.tablesLoaded.has(catalogPathKey("catalog", []))).toBe(
      false,
    );
  });

  it("does not mark deferred namespace stubs with empty children", () => {
    const catalogLoad = hydrateCatalogLoadState({
      databases: [
        {
          name: "catalog",
          dialect: "iceberg",
          children: [
            {
              kind: "namespace",
              name: "top",
              children: [{ kind: "namespace", name: "nested", children: [] }],
            },
          ],
        },
      ],
    });

    expect(
      catalogLoad.childrenLoaded.has(catalogPathKey("catalog", ["top"])),
    ).toBe(true);
    expect(
      catalogLoad.childrenLoaded.has(
        catalogPathKey("catalog", ["top", "nested"]),
      ),
    ).toBe(false);
  });
});
