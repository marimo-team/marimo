/* Copyright 2024 Marimo. All rights reserved. */
import { type AnyMark, Mark } from "./types";

const NON_INTERACTIVE_MARKS = new Set(["boxplot", "errorband", "errorbar"]);

export const Marks = {
  getMarkType(mark: AnyMark): Mark {
    const type = typeof mark === "string" ? mark : mark.type;
    if (NON_INTERACTIVE_MARKS.has(type)) {
      throw new Error("Not supported");
    }
    return type as Mark;
  },
  isInteractive(mark: AnyMark): boolean {
    const type = typeof mark === "string" ? mark : mark.type;
    return !NON_INTERACTIVE_MARKS.has(type);
  },
  makeClickable(mark: AnyMark): AnyMark {
    const type = typeof mark === "string" ? mark : mark.type;
    if (type in Mark) {
      return typeof mark === "string"
        ? { type: mark, cursor: "pointer", tooltip: true }
        : ({ ...mark, type, cursor: "pointer", tooltip: true } as AnyMark);
    }
    return mark;
  },
  getOpacity(mark: AnyMark): number | null {
    if (typeof mark === "string") {
      return null;
    }
    if ("opacity" in mark && typeof mark.opacity === "number") {
      return mark.opacity;
    }
    return null;
  },
};
