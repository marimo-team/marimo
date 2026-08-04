/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { fieldTypesToFilterSchema } from "./schema";

describe("fieldTypesToFilterSchema", () => {
  it("marks unknown fields as invalid", () => {
    expect(fieldTypesToFilterSchema([]).allowUnknownFields).toBe(false);
  });
});
