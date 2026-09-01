/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import {
  getSerializedLayout,
  initialLayoutState,
  layoutStateAtom,
  resolveLayoutType,
} from "../layout";
import { selectLayout } from "../state";

describe("layout state", () => {
  it("falls back to vertical for an unknown layout type", () => {
    expect(initialLayoutState({ type: "unknown", data: {} })).toEqual({
      selectedLayout: "vertical",
      layoutData: {},
    });
  });

  it("preserves pending data until a different layout is selected", () => {
    const state = initialLayoutState({
      type: "slides",
      data: { deck: { transition: "fade" } },
    });

    expect(selectLayout(state, "slides")).toBe(state);
    expect(selectLayout(state, "grid")).toEqual({
      selectedLayout: "grid",
      layoutData: {},
    });
  });

  it.each([
    { isReading: true, expected: "slides" },
    { isReading: false, expected: "vertical" },
  ] as const)(
    "returns $expected when read mode is $isReading",
    ({ isReading, expected }) => {
      expect(
        resolveLayoutType({
          selectedLayout: "vertical",
          isReading,
          searchParams: new URLSearchParams("view-as=slides"),
        }),
      ).toBe(expected);
    },
  );
});

describe("getSerializedLayout", () => {
  beforeEach(() => {
    store.set(layoutStateAtom, initialLayoutState());
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell-1")]: { code: "first = 1" },
          [cellId("cell-2")]: { code: "second = 2" },
        },
      }),
    );
  });

  it("preserves a pending embedded layout when edit mode saves", () => {
    const layout = {
      type: "slides",
      data: {
        cells: [
          { type: "slide", speakerNotes: "Introduce the result" },
          { type: "fragment" },
        ],
        deck: { transition: "fade", verticalAlign: "center" },
      },
    };
    store.set(layoutStateAtom, initialLayoutState(layout));

    expect(getSerializedLayout()).toEqual(layout);
  });

  it("uses the initial layout when materialized data is null", () => {
    store.set(layoutStateAtom, {
      selectedLayout: "slides",
      layoutData: { slides: null },
    });

    expect(getSerializedLayout()).toEqual({
      type: "slides",
      data: { cells: [{}, {}], deck: {} },
    });
  });
});
