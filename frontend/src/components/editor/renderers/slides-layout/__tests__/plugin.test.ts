/* Copyright 2026 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import { SlidesLayoutPlugin } from "../plugin";
import type { CellData } from "@/core/cells/types";
import type { CellId } from "@/core/cells/ids";

function makeCell(id: string, code = "print('hi')"): CellData {
  return {
    id: id as CellId,
    name: id,
    code,
    edited: false,
    lastCodeRun: null,
    lastExecutionTime: null,
    config: { hide_code: false, disabled: false, column: null },
    serializedEditorState: null,
  };
}

describe("SlidesLayoutPlugin validator", () => {
  it("accepts the legacy empty-object shape written by older marimo versions", () => {
    // Backwards compat: any slides file saved before we introduced `cells` /
    // `deck` looks like `{}` on disk. It must still validate.
    expect(SlidesLayoutPlugin.validator.safeParse({}).success).toBe(true);
  });

  it("accepts a fully populated layout", () => {
    expect(
      SlidesLayoutPlugin.validator.safeParse({
        cells: [{ type: "slide" }, {}],
        deck: { transition: "fade" },
      }).success,
    ).toBe(true);
  });

  it("rejects unknown slide types", () => {
    expect(
      SlidesLayoutPlugin.validator.safeParse({
        cells: [{ type: "bogus" }],
      }).success,
    ).toBe(false);
  });
});

describe("SlidesLayoutPlugin deserializeLayout", () => {
  it("returns an empty map when serialized.cells is missing", () => {
    // Regression: previously accessed `serialized.cells.length` on undefined
    // and threw, preventing the app from initializing.
    const layout = SlidesLayoutPlugin.deserializeLayout({}, [makeCell("a")]);
    expect(layout.cells.size).toBe(0);
    expect(layout.deck).toEqual({});
  });

  it("tolerates missing deck", () => {
    const layout = SlidesLayoutPlugin.deserializeLayout(
      { cells: [{ type: "slide" }] },
      [makeCell("a")],
    );
    expect(layout.deck).toEqual({});
    expect(layout.cells.get("a" as CellId)).toEqual({ type: "slide" });
  });

  it("passes through every serialized entry by position (thin passthrough)", () => {
    const layout = SlidesLayoutPlugin.deserializeLayout(
      // Third entry carries an unknown key to prove the deserializer does not
      // strip fields it does not recognize (forward-compat).
      // oxlint-disable-next-line typescript/no-explicit-any
      { cells: [{}, { type: "fragment" }, { notes: "x" } as any] },
      [makeCell("a"), makeCell("b"), makeCell("c")],
    );
    expect([...layout.cells.keys()]).toEqual(["a", "b", "c"]);
    expect(layout.cells.get("a" as CellId)).toEqual({});
    expect(layout.cells.get("b" as CellId)).toEqual({ type: "fragment" });
    expect(layout.cells.get("c" as CellId)).toEqual({ notes: "x" });
  });
});

describe("SlidesLayoutPlugin serializeLayout", () => {
  it("emits one entry per notebook cell (dense, positional)", () => {
    // Even with no per-cell config, the output array must have one slot per
    // notebook cell so positional alignment is preserved on reload.
    const serialized = SlidesLayoutPlugin.serializeLayout(
      { cells: new Map(), deck: {} },
      [makeCell("a"), makeCell("b", "print(42)")],
    );
    expect(serialized.cells).toEqual([{}, {}]);
    expect(serialized.deck).toEqual({});
  });

  it("passes user-set SlideConfig fields through unchanged", () => {
    const cells = [makeCell("a"), makeCell("b"), makeCell("c")];
    const serialized = SlidesLayoutPlugin.serializeLayout(
      {
        cells: new Map([["b" as CellId, { type: "fragment" }]]),
        deck: {},
      },
      cells,
    );
    expect(serialized.cells).toHaveLength(3);
    expect(serialized.cells?.[1]).toMatchObject({ type: "fragment" });
  });

  it("serializes deck config verbatim", () => {
    const serialized = SlidesLayoutPlugin.serializeLayout(
      { cells: new Map(), deck: { transition: "fade" } },
      [makeCell("a")],
    );
    expect(serialized.deck).toEqual({ transition: "fade" });
  });

  it("passes through unknown SlideConfig fields (forward compat)", () => {
    // When a future version adds a new SlideConfig field, serialize should
    // not need updating. Exercise that by stuffing an arbitrary property
    // into the in-memory config and checking it survives.
    const cells = [makeCell("a")];
    // oxlint-disable-next-line typescript/no-explicit-any
    const futureConfig = { type: "slide", notes: "speaker notes" } as any;
    const serialized = SlidesLayoutPlugin.serializeLayout(
      { cells: new Map([["a" as CellId, futureConfig]]), deck: {} },
      cells,
    );
    expect(serialized.cells?.[0]).toMatchObject({
      type: "slide",
      notes: "speaker notes",
    });
  });

  it("round-trips user-set config through serialize + deserialize", () => {
    const cells = [makeCell("a"), makeCell("b")];
    const before = {
      cells: new Map([["b" as CellId, { type: "fragment" as const }]]),
      deck: { transition: "fade" as const },
    };
    const serialized = SlidesLayoutPlugin.serializeLayout(before, cells);
    const after = SlidesLayoutPlugin.deserializeLayout(serialized, cells);
    expect(after.deck).toEqual({ transition: "fade" });
    expect(after.cells.get("b" as CellId)).toMatchObject({ type: "fragment" });
  });
});

/**
 * Frozen snapshots of every on-disk shape this plugin has ever had to parse.
 *
 * RULES FOR THIS BLOCK:
 * - Never delete or modify an existing snapshot — users have `.slides.json`
 *   files in these exact shapes sitting on their disks.
 * - When the on-disk shape evolves, add a new snapshot here (with the release
 *   / commit that introduced it) so we keep proving we can load the old ones.
 * - If you need to change the serializer's output, add a snapshot of the new
 *   shape to `serializedSnapshot` so a diff will surface the change in review.
 *
 * Every snapshot is required to:
 *   1. pass the zod validator (today it is defined but not applied on load;
 *      this guards against regressions once it is),
 *   2. deserialize without throwing,
 *   3. survive a deserialize → serialize → deserialize round trip without
 *      throwing or losing any user-set field carried in the expectations.
 */
interface BackwardsCompatCase {
  label: string;
  input: unknown;
  /**
   * Expected state after deserializing `input` against `cells`. Only asserted
   * properties need to be listed — extra properties are ignored.
   */
  expected: {
    deck?: unknown;
    cellIds: string[];
    cellEntries?: Array<[string, unknown]>;
  };
}

const BACKWARDS_COMPAT_SNAPSHOTS: BackwardsCompatCase[] = [
  {
    // Shape written by every marimo version before we added per-slide config.
    label: "legacy bare {} (pre-slide-config)",
    input: {},
    expected: { deck: {}, cellIds: [] },
  },
  {
    // Current serializer output as of this commit. If you change the
    // serializer, add the new shape as an additional snapshot — don't edit
    // this one.
    label: "current: cells + deck",
    input: {
      cells: [{ type: "slide" }, {}, { type: "fragment" }],
      deck: { transition: "slide" },
    },
    expected: {
      deck: { transition: "slide" },
      cellIds: ["a", "b", "c"],
      cellEntries: [
        ["a", { type: "slide" }],
        ["c", { type: "fragment" }],
      ],
    },
  },
  {
    // Defensive: if a future version adds a new SlideConfig field and a user
    // downgrades, we must not crash on unknown keys.
    label: "forward-compat: unknown SlideConfig fields present",
    input: {
      cells: [{ type: "slide", notes: "x", background: "#000" }],
    },
    expected: {
      deck: {},
      cellIds: ["a"],
      cellEntries: [["a", { type: "slide" }]],
    },
  },
];

describe("SlidesLayoutPlugin backwards compatibility", () => {
  it.each(BACKWARDS_COMPAT_SNAPSHOTS)(
    "loads snapshot: $label",
    ({ input, expected }) => {
      const cells = expected.cellIds.map((id) => makeCell(id));

      // 1. Validator must accept the shape.
      const parsed = SlidesLayoutPlugin.validator.safeParse(input);
      expect(
        parsed.success,
        `validator rejected: ${JSON.stringify(input)}`,
      ).toBe(true);

      // 2. Deserialize must succeed and reflect the user-set fields.
      const layout = SlidesLayoutPlugin.deserializeLayout(
        // Use the raw input (not the validator output) because that is what
        // `deserializeLayout` actually receives in production today.
        // oxlint-disable-next-line typescript/no-explicit-any
        input as any,
        cells,
      );
      if (expected.deck !== undefined) {
        expect(layout.deck).toEqual(expected.deck);
      }
      for (const [cellId, expectedConfig] of expected.cellEntries ?? []) {
        expect(layout.cells.get(cellId as CellId)).toMatchObject(
          expectedConfig as object,
        );
      }

      // 3. Round trip must not throw and must preserve the same user fields.
      const reserialized = SlidesLayoutPlugin.serializeLayout(layout, cells);
      expect(
        SlidesLayoutPlugin.validator.safeParse(reserialized).success,
        `serializer produced a shape that no longer validates: ${JSON.stringify(reserialized)}`,
      ).toBe(true);
      const redeserialized = SlidesLayoutPlugin.deserializeLayout(
        reserialized,
        cells,
      );
      for (const [cellId, expectedConfig] of expected.cellEntries ?? []) {
        expect(redeserialized.cells.get(cellId as CellId)).toMatchObject(
          expectedConfig as object,
        );
      }
      if (expected.deck !== undefined) {
        expect(redeserialized.deck).toEqual(expected.deck);
      }
    },
  );

  it("current serializer output is captured by an inline snapshot", () => {
    // If this snapshot changes you are changing the on-disk shape. That is
    // allowed, but:
    //   1. Add the previous shape to BACKWARDS_COMPAT_SNAPSHOTS above so we
    //      keep proving we can still load it.
    //   2. Update this inline snapshot.
    const cells = [makeCell("a", "print('hello')"), makeCell("b", "x = 1")];
    const serialized = SlidesLayoutPlugin.serializeLayout(
      {
        cells: new Map([
          ["a" as CellId, { type: "slide" }],
          ["b" as CellId, { type: "fragment" }],
        ]),
        deck: { transition: "fade" },
      },
      cells,
    );
    expect(serialized).toMatchInlineSnapshot(`
      {
        "cells": [
          {
            "type": "slide",
          },
          {
            "type": "fragment",
          },
        ],
        "deck": {
          "transition": "fade",
        },
      }
    `);
  });
});
