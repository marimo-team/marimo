/* Copyright 2024 Marimo. All rights reserved. */
import { AnyMark, Mark } from "./types";

export const Marks = {
  getMarkType(mark: AnyMark): Mark {
    const type = typeof mark === "string" ? mark : mark.type;
    if (type === "boxplot" || type === "errorband" || type === "errorbar") {
      throw new Error("Not supported");
    }
    return type;
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
