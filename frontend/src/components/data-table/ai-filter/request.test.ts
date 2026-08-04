/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { extractFilterQuery } from "./request";

describe("extractFilterQuery", () => {
  it("selects the first line that starts with a filter expression", () => {
    expect(
      extractFilterQuery("Here is the filter:\nstatus:open AND priority>=2"),
    ).toBe("status:open AND priority>=2");
    expect(extractFilterQuery("Explanation!\nNOT status:closed")).toBe(
      "NOT status:closed",
    );
    expect(extractFilterQuery("Result:\n(status:open OR status:draft)")).toBe(
      "(status:open OR status:draft)",
    );
  });

  it("does not mistake punctuation in conversational text for a filter", () => {
    expect(extractFilterQuery("Sure!\nHere you go:")).toBe("Sure!");
  });

  it("rejects an empty completion", () => {
    expect(() => extractFilterQuery(" \n\t ")).toThrowError(
      "AI returned an empty filter query.",
    );
  });
});
