/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type {
  SlideConfig,
  SlideType,
} from "@/components/editor/renderers/slides-layout/types";
import type { CellId } from "@/core/cells/ids";
import { composeSlides } from "../compose-slides";
import { buildSubslideNotes, collectBlockNotes } from "../slide-notes";

interface Cell {
  id: CellId;
  type?: SlideType;
}

const cell = (id: string, type?: SlideType): Cell => ({
  id: id as CellId,
  type,
});

const configs = (
  notes: Record<string, string>,
): ReadonlyMap<CellId, SlideConfig> =>
  new Map(
    Object.entries(notes).map(([id, speakerNotes]) => [
      id as CellId,
      { speakerNotes } satisfies SlideConfig,
    ]),
  );

const firstSubslide = (cells: Cell[]) =>
  composeSlides({ cells, getType: (c) => c.type ?? "slide" }).stacks[0]
    .subslides[0];

describe("collectBlockNotes", () => {
  it("concatenates non-empty notes with paragraph spacing", () => {
    const result = collectBlockNotes(
      [cell("a"), cell("b"), cell("c")],
      configs({ a: "first", b: "", c: "third" }),
    );
    expect(result).toBe("first\n\nthird");
  });

  it("returns an empty string when no cell has notes", () => {
    expect(collectBlockNotes([cell("a")], configs({}))).toBe("");
  });

  it("ignores whitespace-only notes", () => {
    expect(
      collectBlockNotes([cell("a"), cell("b")], configs({ a: "   ", b: "x" })),
    ).toBe("x");
  });
});

describe("buildSubslideNotes", () => {
  it("returns empty notes when no cell has any", () => {
    const subslide = firstSubslide([cell("a"), cell("b", "fragment")]);
    expect(buildSubslideNotes(subslide, configs({}))).toEqual({
      slideLevel: "",
      cumulativeByBlock: new Map(),
    });
  });

  it("returns only slide-level notes when there are no fragments", () => {
    const subslide = firstSubslide([cell("a")]);
    expect(buildSubslideNotes(subslide, configs({ a: "intro" }))).toEqual({
      slideLevel: "intro",
      cumulativeByBlock: new Map(),
    });
  });

  it("accumulates fragments below the slide-level notes with a divider", () => {
    const subslide = firstSubslide([
      cell("a"),
      cell("b", "fragment"),
      cell("c", "fragment"),
    ]);
    const { slideLevel, cumulativeByBlock } = buildSubslideNotes(
      subslide,
      configs({ a: "intro", b: "step one", c: "step two" }),
    );
    expect(slideLevel).toBe("intro");
    expect(cumulativeByBlock.get(1)).toBe("intro\n\n---\n\nstep one");
    expect(cumulativeByBlock.get(2)).toBe(
      "intro\n\n---\n\nstep one\n\n---\n\nstep two",
    );
  });

  it("accumulates fragments with no slide-level notes", () => {
    const subslide = firstSubslide([
      cell("a"),
      cell("b", "fragment"),
      cell("c", "fragment"),
    ]);
    const { slideLevel, cumulativeByBlock } = buildSubslideNotes(
      subslide,
      configs({ b: "first reveal", c: "second reveal" }),
    );
    expect(slideLevel).toBe("");
    expect(cumulativeByBlock.get(1)).toBe("first reveal");
    expect(cumulativeByBlock.get(2)).toBe(
      "first reveal\n\n---\n\nsecond reveal",
    );
  });

  it("skips empty fragments without leaving dangling dividers", () => {
    const subslide = firstSubslide([
      cell("a"),
      cell("b", "fragment"),
      cell("c", "fragment"),
    ]);
    const { cumulativeByBlock } = buildSubslideNotes(
      subslide,
      configs({ a: "intro", c: "third" }),
    );
    expect(cumulativeByBlock.get(1)).toBe("intro");
    expect(cumulativeByBlock.get(2)).toBe("intro\n\n---\n\nthird");
  });

  it("returns no cumulative entries when fragments and slide have no notes", () => {
    const subslide = firstSubslide([
      cell("a"),
      cell("b", "fragment"),
      cell("c", "fragment"),
    ]);
    const { cumulativeByBlock } = buildSubslideNotes(subslide, configs({}));
    expect(cumulativeByBlock.size).toBe(0);
  });
});
